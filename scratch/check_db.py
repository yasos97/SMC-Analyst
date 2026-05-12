import sqlite3
try:
    conn = sqlite3.connect('instance/salama_iq.db')
    count = conn.execute('SELECT count(*) FROM "transaction"').fetchone()[0]
    print(f"Total transactions: {count}")
    
    # Also check batch_ids
    batches = conn.execute('SELECT DISTINCT batch_id FROM "transaction"').fetchall()
    print(f"Batches: {batches}")
except Exception as e:
    print(f"Error: {e}")
