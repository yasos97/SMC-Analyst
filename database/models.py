from flask_sqlalchemy import SQLAlchemy
import pandas as pd

db = SQLAlchemy()

class Transaction(db.Model):
    __tablename__ = 'transaction'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    batch_id = db.Column(db.String(50), nullable=False) # Permet de tracer/effacer un lot d'upload
    
    datetransaction = db.Column(db.DateTime, nullable=True)
    client = db.Column(db.String(200), nullable=True)
    statut = db.Column(db.String(200), nullable=True)
    
    volume_gasoil = db.Column(db.Float, default=0.0)
    volume_super = db.Column(db.Float, default=0.0)
    
    marge_ht = db.Column(db.Float, nullable=True)
    ca_total = db.Column(db.Float, nullable=True)
    ca = db.Column(db.Float, nullable=True)
    achat_ht = db.Column(db.Float, nullable=True)
    
    prix_achat_gasoil_ht = db.Column(db.Float, nullable=True)
    prix_achat_super_ht = db.Column(db.Float, nullable=True)
    prix_vente_gasoil_ttc = db.Column(db.Float, nullable=True)
    prix_vente_super_ttc = db.Column(db.Float, nullable=True)
    prix_vente_gasoil_ht = db.Column(db.Float, nullable=True)
    prix_vente_super_ht = db.Column(db.Float, nullable=True)
    marge_unitaire = db.Column(db.Float, nullable=True)

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
    # Plus rapide: utilise DELETE FROM au lieu de query().delete()
    db.session.execute(db.delete(Transaction))
    db.session.commit()
    # Force la libération de la mémoire
    db.session.expire_all()
