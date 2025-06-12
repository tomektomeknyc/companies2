import os
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import json

# Database setup
DATABASE_URL = os.getenv('DATABASE_URL')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database Models
class Company(Base):
    __tablename__ = "companies"
    
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(20), unique=True, index=True)
    company_name = Column(String(200))
    country = Column(String(10))
    sector = Column(String(100))
    industry = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class FinancialData(Base):
    __tablename__ = "financial_data"
    
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(20), index=True)
    year = Column(Integer)
    ebitda = Column(Float)
    capex = Column(Float)
    debt = Column(Float)
    cash = Column(Float)
    enterprise_value = Column(Float)
    cash_taxes_paid = Column(Float)
    change_nwc = Column(Float)
    interest_expense = Column(Float)
    tax_rate = Column(Float)
    fcff = Column(Float)
    fcfe = Column(Float)
    fcf = Column(Float)
    ev_ebitda = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

class FactorData(Base):
    __tablename__ = "factor_data"
    
    id = Column(Integer, primary_key=True, index=True)
    region = Column(String(100))
    date = Column(DateTime)
    mkt_rf = Column(Float)  # Market minus Risk-free
    smb = Column(Float)     # Small minus Big
    hml = Column(Float)     # High minus Low
    rmw = Column(Float)     # Robust minus Weak
    cma = Column(Float)     # Conservative minus Aggressive
    rf = Column(Float)      # Risk-free rate
    created_at = Column(DateTime, default=datetime.utcnow)

class BetaAnalysis(Base):
    __tablename__ = "beta_analysis"
    
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(20), index=True)
    model_type = Column(String(10))  # 'CAPM' or 'FF5'
    analysis_date = Column(DateTime, default=datetime.utcnow)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    
    # Regression results
    alpha = Column(Float)
    market_beta = Column(Float)
    smb_beta = Column(Float, nullable=True)
    hml_beta = Column(Float, nullable=True)
    rmw_beta = Column(Float, nullable=True)
    cma_beta = Column(Float, nullable=True)
    r_squared = Column(Float)
    observations = Column(Integer)
    
    # Additional metrics
    wacc = Column(Float)
    risk_free_rate = Column(Float)
    market_premium = Column(Float)

class SimulationHistory(Base):
    __tablename__ = "simulation_history"
    
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(20), index=True)
    user_session = Column(String(100))
    simulation_date = Column(DateTime, default=datetime.utcnow)
    
    # Simulation parameters
    ebitda_change = Column(Float)
    capex_change = Column(Float)
    debt_change = Column(Float)
    cash_change = Column(Float)
    nwc_change = Column(Float)
    ev_ebitda_change = Column(Float)
    
    # Results
    simulated_metrics = Column(JSON)
    original_metrics = Column(JSON)

class StockReturns(Base):
    __tablename__ = "stock_returns"
    
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(20), index=True)
    date = Column(DateTime)
    monthly_return = Column(Float)
    excess_return = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

# Database helper functions
def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_database():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)

def store_financial_data(df: pd.DataFrame):
    """Store financial data from DataFrame to database"""
    db = SessionLocal()
    try:
        for _, row in df.iterrows():
            financial_record = FinancialData(
                ticker=row['Ticker'],
                year=row['Year'],
                ebitda=row['EBITDA'],
                capex=row['CapEx'],
                debt=row['Debt'],
                cash=row['Cash'],
                enterprise_value=row['EV'],
                cash_taxes_paid=row['CashTaxesPaid'],
                change_nwc=row['ChangeNWC'],
                interest_expense=row['InterestExpense'],
                tax_rate=row['tax_rate'],
                fcff=row['FCFF'],
                fcfe=row['FCFE'],
                fcf=row['FCF'],
                ev_ebitda=row['EV/EBITDA']
            )
            
            # Check if record exists
            existing = db.query(FinancialData).filter(
                FinancialData.ticker == row['Ticker'],
                FinancialData.year == row['Year']
            ).first()
            
            if not existing:
                db.add(financial_record)
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

def store_company_info(ticker: str, country: str, company_name: str = None):
    """Store company information"""
    db = SessionLocal()
    try:
        existing = db.query(Company).filter(Company.ticker == ticker).first()
        if not existing:
            company = Company(
                ticker=ticker,
                company_name=company_name or ticker,
                country=country.upper()
            )
            db.add(company)
            db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

def store_factor_data(region: str, factor_df: pd.DataFrame):
    """Store Fama-French factor data"""
    db = SessionLocal()
    try:
        for date_idx, row in factor_df.iterrows():
            factor_record = FactorData(
                region=region,
                date=date_idx,
                mkt_rf=row['Mkt-RF'],
                smb=row['SMB'],
                hml=row['HML'],
                rmw=row['RMW'],
                cma=row['CMA'],
                rf=row['RF']
            )
            
            # Check if record exists
            existing = db.query(FactorData).filter(
                FactorData.region == region,
                FactorData.date == date_idx
            ).first()
            
            if not existing:
                db.add(factor_record)
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

def store_beta_analysis(ticker: str, model_type: str, betas: dict, wacc: float = None):
    """Store beta analysis results"""
    db = SessionLocal()
    try:
        beta_record = BetaAnalysis(
            ticker=ticker,
            model_type=model_type,
            alpha=betas.get('alpha'),
            market_beta=betas.get('market_beta'),
            smb_beta=betas.get('smb_beta'),
            hml_beta=betas.get('hml_beta'),
            rmw_beta=betas.get('rmw_beta'),
            cma_beta=betas.get('cma_beta'),
            r_squared=betas.get('r_squared'),
            observations=betas.get('observations'),
            wacc=wacc
        )
        db.add(beta_record)
        db.commit()
        return beta_record.id
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

def store_simulation(ticker: str, session_id: str, sim_params: dict, results: dict):
    """Store simulation parameters and results"""
    db = SessionLocal()
    try:
        simulation = SimulationHistory(
            ticker=ticker,
            user_session=session_id,
            ebitda_change=sim_params.get('ebitda_change', 0),
            capex_change=sim_params.get('capex_change', 0),
            debt_change=sim_params.get('debt_change', 0),
            cash_change=sim_params.get('cash_change', 0),
            nwc_change=sim_params.get('nwc_change', 0),
            ev_ebitda_change=sim_params.get('ev_ebitda_change', 0),
            simulated_metrics=results.get('simulated'),
            original_metrics=results.get('original')
        )
        db.add(simulation)
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

def store_stock_returns(ticker: str, returns_df: pd.DataFrame):
    """Store stock returns data"""
    db = SessionLocal()
    try:
        for date_idx, return_val in returns_df.items():
            stock_return = StockReturns(
                ticker=ticker,
                date=date_idx,
                monthly_return=return_val
            )
            
            # Check if record exists
            existing = db.query(StockReturns).filter(
                StockReturns.ticker == ticker,
                StockReturns.date == date_idx
            ).first()
            
            if not existing:
                db.add(stock_return)
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

def get_financial_data(ticker: str = None) -> pd.DataFrame:
    """Retrieve financial data from database"""
    db = SessionLocal()
    try:
        query = db.query(FinancialData)
        if ticker:
            query = query.filter(FinancialData.ticker == ticker)
        
        results = query.all()
        
        data = []
        for record in results:
            data.append({
                'Ticker': record.ticker,
                'Year': record.year,
                'EBITDA': record.ebitda,
                'CapEx': record.capex,
                'Debt': record.debt,
                'Cash': record.cash,
                'EV': record.enterprise_value,
                'CashTaxesPaid': record.cash_taxes_paid,
                'ChangeNWC': record.change_nwc,
                'InterestExpense': record.interest_expense,
                'tax_rate': record.tax_rate,
                'FCFF': record.fcff,
                'FCFE': record.fcfe,
                'FCF': record.fcf,
                'EV/EBITDA': record.ev_ebitda
            })
        
        return pd.DataFrame(data)
    finally:
        db.close()

def get_factor_data(region: str) -> pd.DataFrame:
    """Retrieve factor data from database"""
    db = SessionLocal()
    try:
        query = db.query(FactorData).filter(FactorData.region == region)
        results = query.all()
        
        data = []
        for record in results:
            data.append({
                'Date': record.date,
                'Mkt-RF': record.mkt_rf,
                'SMB': record.smb,
                'HML': record.hml,
                'RMW': record.rmw,
                'CMA': record.cma,
                'RF': record.rf
            })
        
        df = pd.DataFrame(data)
        if not df.empty:
            df.set_index('Date', inplace=True)
        return df
    finally:
        db.close()

def get_latest_beta_analysis(ticker: str, model_type: str = None) -> dict:
    """Get latest beta analysis for a ticker"""
    db = SessionLocal()
    try:
        query = db.query(BetaAnalysis).filter(BetaAnalysis.ticker == ticker)
        if model_type:
            query = query.filter(BetaAnalysis.model_type == model_type)
        
        result = query.order_by(BetaAnalysis.analysis_date.desc()).first()
        
        if result:
            return {
                'alpha': result.alpha,
                'market_beta': result.market_beta,
                'smb_beta': result.smb_beta,
                'hml_beta': result.hml_beta,
                'rmw_beta': result.rmw_beta,
                'cma_beta': result.cma_beta,
                'r_squared': result.r_squared,
                'observations': result.observations,
                'wacc': result.wacc,
                'model_type': result.model_type,
                'analysis_date': result.analysis_date
            }
        return None
    finally:
        db.close()

def get_simulation_history(ticker: str, limit: int = 10) -> list:
    """Get simulation history for a ticker"""
    db = SessionLocal()
    try:
        results = db.query(SimulationHistory).filter(
            SimulationHistory.ticker == ticker
        ).order_by(SimulationHistory.simulation_date.desc()).limit(limit).all()
        
        history = []
        for record in results:
            history.append({
                'date': record.simulation_date,
                'parameters': {
                    'ebitda_change': record.ebitda_change,
                    'capex_change': record.capex_change,
                    'debt_change': record.debt_change,
                    'cash_change': record.cash_change,
                    'nwc_change': record.nwc_change,
                    'ev_ebitda_change': record.ev_ebitda_change
                },
                'simulated_metrics': record.simulated_metrics,
                'original_metrics': record.original_metrics
            })
        
        return history
    finally:
        db.close()

def get_companies() -> list:
    """Get list of all companies"""
    db = SessionLocal()
    try:
        results = db.query(Company).all()
        return [{
            'ticker': comp.ticker,
            'name': comp.company_name,
            'country': comp.country,
            'sector': comp.sector,
            'industry': comp.industry
        } for comp in results]
    finally:
        db.close()