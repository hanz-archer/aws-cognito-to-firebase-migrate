import firebase_admin
from firebase_admin import auth, credentials, firestore
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='migration.log'
)

def get_attribute_value(attributes: list, name: str) -> Optional[str]:
    """Helper function to get attribute value from Cognito user attributes."""
    return next((attr["Value"] for attr in attributes if attr["Name"] == name), None)

def create_firestore_user_data(user_data: Dict[str, Any], user_record: auth.UserRecord) -> Dict[str, Any]:
    """Create Firestore user document data preserving all Cognito attributes."""
    attributes = user_data["Attributes"]
    
    # Create exact Cognito data structure in Firestore
    return {
        "Username": user_data["Username"],  # Original Cognito Username
        "Attributes": {
            "email": get_attribute_value(attributes, "email"),
            "email_verified": get_attribute_value(attributes, "email_verified") == "true",
            "phone_number": get_attribute_value(attributes, "phone_number"),
            "phone_number_verified": get_attribute_value(attributes, "phone_number_verified") == "true",
            "family_name": get_attribute_value(attributes, "family_name"),
            "given_name": get_attribute_value(attributes, "given_name"),
            "sub": get_attribute_value(attributes, "sub")
        },
        "UserCreateDate": user_data["UserCreateDate"],
        "UserLastModifiedDate": user_data["UserLastModifiedDate"],
        "Enabled": user_data["Enabled"],
        "UserStatus": user_data["UserStatus"],
        # Add Firebase specific fields
        "firebase_uid": user_record.uid
    }

def migrate_user(user_data: Dict[str, Any], db: firestore.Client) -> Optional[auth.UserRecord]:
    """Migrate a user to both Firebase Auth and Firestore."""
    attributes = user_data["Attributes"]
    
    # Get required fields
    email = get_attribute_value(attributes, "email")
    email_verified = get_attribute_value(attributes, "email_verified")
    phone_number = get_attribute_value(attributes, "phone_number")
    given_name = get_attribute_value(attributes, "given_name")
    family_name = get_attribute_value(attributes, "family_name")
    
    if not email:
        logging.warning(f"Skipping user: No email found")
        return None

    try:
        # 1. Create Firebase Auth user with all supported fields
        user_kwargs = {
            "uid": user_data["Username"],  # Use Cognito Username as Firebase UID
            "email": email,
            "password": "Default@123",
            "email_verified": email_verified.lower() == "true" if email_verified else False,
            "display_name": f"{given_name} {family_name}".strip() if given_name or family_name else None,
            "disabled": not user_data["Enabled"]
        }
        
        # Only add phone number if it exists
        if phone_number:
            user_kwargs["phone_number"] = phone_number
        
        # Remove None values
        user_kwargs = {k: v for k, v in user_kwargs.items() if v is not None}
        
        try:
            # Check if user exists in Auth
            user_record = auth.get_user_by_email(email)
            logging.info(f"User {email} already exists in Auth")
        except auth.UserNotFoundError:
            try:
                # First try to create user with phone number (if provided)
                user_record = auth.create_user(**user_kwargs)
                logging.info(f"Created Auth user with phone: {email}")
            except Exception as e:
                if "INVALID_PHONE_NUMBER" in str(e) or "PHONE_NUMBER_EXISTS" in str(e):
                    # If phone number is invalid or exists, try again without phone
                    logging.warning(f"Phone number issue for {email}: {str(e)}. Creating user without phone.")
                    user_kwargs.pop('phone_number', None)
                    user_record = auth.create_user(**user_kwargs)
                    logging.info(f"Created Auth user without phone: {email}")
                else:
                    # If it's a different error, raise it
                    raise
            
            # Generate password reset link
            reset_link = auth.generate_password_reset_link(email)
            logging.info(f"Password reset link for {email}: {reset_link}")
        
        # 2. Store complete Cognito data structure in Firestore (including phone number)
        users_ref = db.collection('users')
        user_doc_ref = users_ref.document(user_record.uid)
        
        # Create or update Firestore document with exact Cognito structure
        firestore_data = create_firestore_user_data(user_data, user_record)
        user_doc_ref.set(firestore_data, merge=True)
        logging.info(f"Updated Firestore data for user: {email}")
        
        return user_record
            
    except Exception as e:
        logging.error(f"Error migrating user {email}: {str(e)}")
        return None

def delete_firestore_users():
    """Delete all users from Firestore."""
    try:
        # Initialize Firebase Admin SDK if not already initialized
        try:
            app = firebase_admin.get_app()
        except ValueError:
            cred = credentials.Certificate("service-account.json")
            firebase_admin.initialize_app(cred)
        
        # Initialize Firestore
        db = firestore.client()
        
        # Get all users from Firestore
        deleted_count = 0
        failed_count = 0
        
        # Delete users collection
        users_ref = db.collection('users')
        docs = users_ref.stream()
        
        for doc in docs:
            try:
                doc.reference.delete()
                logging.info(f"Deleted Firestore data for user: {doc.id}")
                deleted_count += 1
            except Exception as e:
                logging.error(f"Failed to delete Firestore data for user {doc.id}: {str(e)}")
                failed_count += 1
        
        logging.info(f"Firestore deletion completed! Deleted: {deleted_count}, Failed: {failed_count}")
        return deleted_count, failed_count
        
    except Exception as e:
        logging.error(f"Fatal error during Firestore deletion: {str(e)}")
        raise

def delete_auth_users(delete_firestore=True):
    """Delete users from Firebase Authentication and optionally from Firestore."""
    try:
        # Initialize Firebase Admin SDK if not already initialized
        try:
            app = firebase_admin.get_app()
        except ValueError:
            cred = credentials.Certificate("service-account.json")
            firebase_admin.initialize_app(cred)
        
        # Delete Firestore data first if requested
        if delete_firestore:
            firestore_deleted, firestore_failed = delete_firestore_users()
            logging.info(f"Firestore deletion: Deleted {firestore_deleted}, Failed {firestore_failed}")
        
        # Get all users from Firebase Auth
        auth_deleted = 0
        auth_failed = 0
        
        # Delete users in batches (Firebase has a limit of 1000 users per batch)
        page = auth.list_users()
        while page:
            for user in page.users:
                try:
                    # Delete from Authentication
                    auth.delete_user(user.uid)
                    logging.info(f"Deleted auth user {user.email} (UID: {user.uid})")
                    auth_deleted += 1
                except Exception as e:
                    logging.error(f"Failed to delete auth user {user.email}: {str(e)}")
                    auth_failed += 1
            
            # Get next batch of users
            page = page.get_next_page()
        
        logging.info(f"Auth deletion completed! Deleted: {auth_deleted}, Failed: {auth_failed}")
        return auth_deleted, auth_failed
        
    except Exception as e:
        logging.error(f"Fatal error during deletion: {str(e)}")
        raise

def main():
    """Main function with added deletion option."""
    try:
        while True:
            action = input("Choose action (1: Migrate users, 2: Delete users, 3: Exit): ")
            
            if action == "1":
                # Initialize Firebase Admin SDK
                try:
                    app = firebase_admin.get_app()
                except ValueError:
                    cred = credentials.Certificate("service-account.json")
                    firebase_admin.initialize_app(cred)
                
                # Initialize Firestore
                db = firestore.client()
                
                # Load Cognito users
                with open("cognito_users.json", "r") as f:
                    cognito_data = json.load(f)
                
                # Track migration statistics
                stats = {
                    "total": len(cognito_data["Users"]),
                    "success": 0,
                    "failed": 0
                }
                
                # Process users
                for user in cognito_data["Users"]:
                    result = migrate_user(user, db)
                    if result:
                        stats["success"] += 1
                    else:
                        stats["failed"] += 1
                
                # Log final statistics
                logging.info("Migration completed!")
                logging.info(f"Total users processed: {stats['total']}")
                logging.info(f"Successfully migrated: {stats['success']}")
                logging.info(f"Failed to migrate: {stats['failed']}")
            
            elif action == "2":
                delete_type = input("Delete from (1: Both Auth and Firestore, 2: Auth only, 3: Firestore only): ")
                confirm = input("Are you sure? This will permanently delete the data (yes/no): ")
                
                if confirm.lower() == "yes":
                    if delete_type == "1":
                        auth_deleted, auth_failed = delete_auth_users(delete_firestore=True)
                        print(f"Deleted from Auth: {auth_deleted}, Failed: {auth_failed}")
                    elif delete_type == "2":
                        auth_deleted, auth_failed = delete_auth_users(delete_firestore=False)
                        print(f"Deleted from Auth: {auth_deleted}, Failed: {auth_failed}")
                    elif delete_type == "3":
                        firestore_deleted, firestore_failed = delete_firestore_users()
                        print(f"Deleted from Firestore: {firestore_deleted}, Failed: {firestore_failed}")
                    else:
                        print("Invalid option")
                else:
                    print("Deletion cancelled")
            
            elif action == "3":
                print("Exiting...")
                break
            
            else:
                print("Invalid option. Please choose 1, 2, or 3")
                
    except Exception as e:
        logging.error(f"Fatal error: {str(e)}")
        raise

if __name__ == "__main__":
    main()