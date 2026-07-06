from flask_sqlalchemy import SQLAlchemy
import pandas as pd

db = SQLAlchemy()

class Vente(db.Model):
    __tablename__ = 'vente'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    batch_id = db.Column(db.String(50), nullable=False)

    datetransaction = db.Column(db.DateTime, nullable=True)
    client = db.Column(db.String(200), nullable=True)
    fournisseur = db.Column(db.String(200), nullable=True)
    statut = db.Column(db.String(200), nullable=True)
    
    volume_gasoil = db.Column(db.Float, default=0.0)
    volume_super = db.Column(db.Float, default=0.0)
    
    ca_total = db.Column(db.Float, nullable=True)
    ca = db.Column(db.Float, nullable=True)
    marge_ht = db.Column(db.Float, nullable=True)
    achat_ht = db.Column(db.Float, nullable=True)

    prix_achat_gasoil_ht = db.Column(db.Float, nullable=True)
    prix_achat_super_ht = db.Column(db.Float, nullable=True)
    prix_vente_gasoil_ttc = db.Column(db.Float, nullable=True)
    prix_vente_super_ttc = db.Column(db.Float, nullable=True)
    prix_vente_gasoil_ht = db.Column(db.Float, nullable=True)
    prix_vente_super_ht = db.Column(db.Float, nullable=True)
    marge_unitaire = db.Column(db.Float, nullable=True)


class Achat(db.Model):
    __tablename__ = 'achat'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    batch_id = db.Column(db.String(50), nullable=False)

    datetransaction = db.Column(db.DateTime, nullable=True)
    fournisseur = db.Column(db.String(200), nullable=True)
    statut = db.Column(db.String(200), nullable=True)
    
    volume_gasoil = db.Column(db.Float, default=0.0)
    volume_super = db.Column(db.Float, default=0.0)
    
    achat_ht = db.Column(db.Float, nullable=True)
    prix_achat_gasoil_ht = db.Column(db.Float, nullable=True)
    prix_achat_super_ht = db.Column(db.Float, nullable=True)


class Paiement(db.Model):
    """Mouvement d'argent saisi manuellement (encaissement client ou paiement fournisseur)."""
    __tablename__ = 'paiement'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sens = db.Column(db.String(20), nullable=False)        # 'encaissement' | 'paiement'
    tiers_type = db.Column(db.String(20), nullable=False)  # 'client' | 'fournisseur'
    tiers = db.Column(db.String(200), nullable=False)
    montant = db.Column(db.Float, nullable=False, default=0.0)
    date_paiement = db.Column(db.DateTime, nullable=True)
    mode = db.Column(db.String(30), nullable=True)         # virement | espèces | chèque | traite
    note = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, nullable=True)


class SoldeInitial(db.Model):
    """Solde d'ouverture par tiers (ardoise antérieure aux données importées)."""
    __tablename__ = 'solde_initial'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tiers_type = db.Column(db.String(20), nullable=False)  # 'client' | 'fournisseur'
    tiers = db.Column(db.String(200), nullable=False)
    montant = db.Column(db.Float, nullable=False, default=0.0)
    __table_args__ = (db.UniqueConstraint('tiers_type', 'tiers', name='uix_tiers'),)





def init_db(app):
    db.init_app(app)
    with app.app_context():
        db.create_all()

def load_ventes():
    query = db.session.query(Vente).statement
    return pd.read_sql(query, db.engine)

def load_achats():
    query = db.session.query(Achat).statement
    return pd.read_sql(query, db.engine)

def clear_database():
    """Vide toutes les données (cas d'erreur)."""
    db.session.execute(db.delete(Vente))
    db.session.execute(db.delete(Achat))
    db.session.commit()
    db.session.expire_all()


def load_paiements() -> pd.DataFrame:
    """DataFrame de tous les paiements/encaissements saisis."""
    query = db.session.query(Paiement).statement
    return pd.read_sql(query, db.engine)


def load_soldes_initiaux() -> pd.DataFrame:
    """DataFrame des soldes d'ouverture par tiers."""
    query = db.session.query(SoldeInitial).statement
    return pd.read_sql(query, db.engine)
