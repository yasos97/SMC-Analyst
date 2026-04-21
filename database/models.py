from flask_sqlalchemy import SQLAlchemy
import pandas as pd

db = SQLAlchemy()

class Transaction(db.Model):
    __tablename__ = 'transaction'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    batch_id = db.Column(db.String(50), nullable=False) # Permet de tracer/effacer un lot d'upload
    
    datetransaction = db.Column(db.DateTime, nullable=True)
    client = db.Column(db.String(200), nullable=True)
    fournisseur = db.Column(db.String(200), nullable=True)
    produit = db.Column(db.String(100), nullable=True)
    
    volume_gasoil = db.Column(db.Float, default=0.0)
    volume_super = db.Column(db.Float, default=0.0)
    ca_total = db.Column(db.Float, default=0.0)
    marge_ht = db.Column(db.Float, default=0.0)

def init_db(app):
    db.init_app(app)
    with app.app_context():
        db.create_all()

def load_all_transactions():
    """Génère un DataFrame Pandas à partir de la base SQLite entière."""
    query = db.session.query(Transaction).statement
    df = pd.read_sql(query, db.engine)
    return df

def clear_database():
    """Vide toutes les données (cas d'erreur)."""
    db.session.query(Transaction).delete()
    db.session.commit()
