Firebase Auth & Firestore Migration from AWS Cognito
====================================================

📌 Overview
-----------

This script migrates user data from **AWS Cognito** to **Firebase Authentication** and **Firestore**. It ensures that all user attributes from Cognito are preserved in Firestore while maintaining compatibility with Firebase Auth.

🚀 Features
-----------

*   ✅ Migrate users from AWS Cognito JSON export to Firebase Auth.
    
*   ✅ Store user attributes in Firestore while maintaining Cognito's structure.
    
*   ✅ Handle existing Firebase users gracefully.
    
*   ✅ Provide password reset links for migrated users.
    
*   ✅ Support deletion of users from Firebase Auth and/or Firestore.
    
*   ✅ Log migration results for auditing.
    

🔧 Requirements
---------------

*   **Python 3.x**
    
*   **Firebase Admin SDK**
    
*   **AWS Cognito user export in JSON format**
    
*   **Firebase project with a service account JSON file**
    

📂 Setup
--------

1.  pip install firebase-admin google-cloud-firestore
    
2.  Obtain your Firebase **service account JSON file** from Firebase Console.
    
3.  Save the service account JSON file as service-account.json in the script directory.
    
4.  Export AWS Cognito users to cognito\_users.json.
    

▶️ Usage
--------

Run the script and follow the prompts:
To run the script, use the following command:

```bash
python migrate_users.py

### Options:

1️⃣ Migrate users from AWS Cognito to Firebase.2️⃣ Delete users from Firebase Auth and/or Firestore.3️⃣ Exit.

📜 Expected Cognito JSON Format
-------------------------------

The script expects a JSON file structured like this:

```json
{
  "Users": [
    {
      "Username": "1234567890",
      "Attributes": [
        { "Name": "email", "Value": "user@example.com" },
        { "Name": "email_verified", "Value": "true" },
        { "Name": "phone_number", "Value": "+1234567890" },
        { "Name": "phone_number_verified", "Value": "true" },
        { "Name": "given_name", "Value": "John" },
        { "Name": "family_name", "Value": "Doe" },
        { "Name": "sub", "Value": "abcd-efgh-ijkl" }
      ],
      "UserCreateDate": "2023-01-01T12:00:00Z",
      "UserLastModifiedDate": "2023-06-01T12:00:00Z",
      "Enabled": true,
      "UserStatus": "CONFIRMED"
    }
  ]
}


🔄 How It Works
---------------

1️⃣ Reads user data from cognito\_users.json.2️⃣ Creates or updates users in Firebase Authentication.3️⃣ Stores full Cognito attribute data in Firestore under users/{firebase\_uid}.4️⃣ Generates a **password reset link** for the user.5️⃣ Logs migration details in migration.log.

✏️ Customization
----------------

*   Modify the migrate\_user() function to add additional Cognito attributes.
    
*   Change **default passwords** or implement a **custom password policy**.
    
*   Adjust Firestore document structure to match your application's needs.
    

❌ Deleting Users
----------------

To remove migrated users from Firebase, select option 2 when running the script. You can choose to:

*   🗑 **Delete users from both Firebase Auth and Firestore**.
    
*   🔥 **Delete users from Firebase Auth only**.
    
*   📂 **Delete users from Firestore only**.
    

📝 Logging
----------

All operations are logged in migration.log for **debugging** and **auditing**.

⚠️ Notes
--------

*   Users **without an email** are skipped (**Firebase requires an email for authentication**).
    
*   If a **phone number** is invalid or already exists, the migration retries without it.
    
*   Firebase does not support all Cognito attributes natively; therefore, extra attributes are stored in Firestore.
    

📜 License
----------

This script is **open-source**. Modify and use it as needed for your project.

💡 Need help? Feel free to ask! 🚀
