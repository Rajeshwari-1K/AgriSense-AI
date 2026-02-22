from pymongo import MongoClient
import sys

def test_mongodb():
    print("🔍 Testing MongoDB Connection...")
    print("=" * 50)
    
    try:
        # Try to connect to MongoDB
        client = MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=5000)
        
        # Test connection with timeout
        client.admin.command('ping')
        print("✅ MongoDB is running and connected!")
        
        # Check if our database exists
        db = client['agrisense']
        print(f"✅ Database 'agrisense' accessible")
        
        # List all databases
        databases = client.list_database_names()
        print("📊 Available databases:", databases)
        
        # Check collections in our database
        collections = db.list_collection_names()
        print("📁 Collections in 'agrisense':", collections)
        
        # Count users and predictions
        users_count = db.users.count_documents({})
        predictions_count = db.predictions.count_documents({})
        
        print(f"👥 Users in database: {users_count}")
        print(f"🌱 Predictions in database: {predictions_count}")
        
        # Show sample users (without passwords)
        if users_count > 0:
            print("\n📋 Sample users:")
            users = db.users.find({}, {'password': 0}).limit(3)
            for user in users:
                print(f"  - {user.get('name', 'No name')} ({user.get('email', 'No email')})")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"❌ MongoDB connection failed: {str(e)}")
        print("\n💡 Troubleshooting steps:")
        print("1. Make sure MongoDB is installed")
        print("2. Start MongoDB service:")
        print("   - Windows: Run 'mongod' in Command Prompt as Administrator")
        print("   - Mac: Run 'brew services start mongodb-community'")
        print("   - Linux: Run 'sudo systemctl start mongod'")
        print("3. Or download MongoDB Compass: https://www.mongodb.com/try/download/compass")
        return False

if __name__ == "__main__":
    test_mongodb()
    
    print("\n" + "=" * 50)
    input("Press Enter to close...")