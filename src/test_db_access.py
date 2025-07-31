import sqlite3

# Try to connect and query the database
try:
    conn = sqlite3.connect('data/thesis_app.db')
    cursor = conn.cursor()
    
    print("✅ Database connection successful!")
    
    # Test a simple query
    cursor.execute("SELECT COUNT(*) FROM model_capabilities")
    count = cursor.fetchone()[0]
    print(f"✅ Query successful! ModelCapability count: {count}")
    
    # Test data retrieval
    cursor.execute("SELECT model_id, provider, model_name FROM model_capabilities LIMIT 3")
    models = cursor.fetchall()
    print("✅ Sample data:")
    for model in models:
        print(f"   {model[0]} ({model[1]}) - {model[2]}")
    
    conn.close()
    print("✅ Database is fully accessible!")
    
except Exception as e:
    print(f"❌ Database error: {e}")
