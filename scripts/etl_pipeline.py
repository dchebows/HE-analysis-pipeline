#!/usr/bin/env python3
"""
Hedgeye Risk Range ETL Pipeline - GitHub Actions Version
Runs Monday-Friday to process HTML files and generate enriched datasets
"""

import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import yfinance as yf
from pathlib import Path
from datetime import datetime, timedelta
import shutil
import logging
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# CONFIGURATION
# ============================================================

CONFIG = {
    'base_path': 'Risk_Range_Data',
    'master_filename': 'risk_ranges_master.csv',
    
    'tracked_tickers': [
        'UST10Y', 'SPX', 'COMPQ', 'RUT', 'VIX',
        'USD', 'GOLD', 'AAPL', 'BITCOIN'
    ],
    
    'enrichment': {
        'start_date': '2017-01-02',
        
        'yahoo_tickers': {
            'SPX': '^GSPC',
            'GOLD': 'GC=F',
            'UST10Y': '^TNX',
            'COMPQ': '^IXIC',
            'RUT': '^RUT',
            'VIX': '^VIX',
            'USD': 'DX-Y.NYB',
            'AAPL': 'AAPL',
            'BITCOIN': 'BTC-USD',
        },
        
        'volatility_tickers': {
            'SPX': '^VIX',
            'GOLD': '^GVZ',
            'UST10Y': '^VIX',
            'COMPQ': '^VIX',
            'RUT': '^VIX',
            'VIX': '^VIX',
            'USD': '^VIX',
            'AAPL': '^VIX',
            'BITCOIN': '^VIX',
        },
        
        'ohlc_column_mapping': {
            'SPX': 'GSPC',
            'GOLD': 'GC',
            'UST10Y': 'TNX',
            'COMPQ': 'IXIC',
            'RUT': 'RUT',
            'VIX': 'VIX',
            'USD': 'DX',
            'AAPL': 'AAPL',
            'BITCOIN': 'BTC',
        },
        
        'vol_column_mapping': {
            'SPX': 'VIX',
            'GOLD': 'GVZ',
            'UST10Y': 'VIX',
            'COMPQ': 'VIX',
            'RUT': 'VIX',
            'VIX': 'VIXI',
            'USD': 'VIX',
            'AAPL': 'VIX',
            'BITCOIN': 'VIX',
        }
    },
    
    'pipeline': {
        'auto_enrich_all': True,
        'smart_detection': True,
        'backup_before_merge': True,
        'max_retries': 3,
        'skip_malformed_html': True,
    }
}

# ============================================================
# SETUP PATHS
# ============================================================

BASE_PATH = Path(CONFIG['base_path'])

PATHS = {
    'raw_html': BASE_PATH / '00_raw_html',
    'processed': BASE_PATH / '01_processed',
    'master': BASE_PATH / '02_master',
    'tickers': BASE_PATH / '03_tickers',
    'enriched': BASE_PATH / '04_enriched',
    'logs': BASE_PATH / 'logs',
    'metadata': BASE_PATH / '.metadata',
}

# Create directories
for path in PATHS.values():
    path.mkdir(parents=True, exist_ok=True)

# ============================================================
# LOGGING SETUP
# ============================================================

log_filename = f"etl_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
log_path = PATHS['logs'] / log_filename

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-5s | %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.FileHandler(log_path, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('ETLPipeline')

# ============================================================
# CHANGE DETECTOR
# ============================================================

class ChangeDetector:
    """Detects when downstream files need regeneration"""
    
    def __init__(self, paths):
        self.paths = paths
        self.master_path = paths['master'] / CONFIG['master_filename']
        self.processed_tracker = paths['raw_html'] / 'processed_files.txt'
    
    def get_file_mtime(self, file_path):
        if not file_path.exists():
            return 0
        return file_path.stat().st_mtime
    
    def get_new_html_files(self):
        html_files = (
            list(self.paths['raw_html'].glob('*.html')) +
            list(self.paths['raw_html'].glob('*.htm'))
        )
        
        processed = set()
        if self.processed_tracker.exists():
            with open(self.processed_tracker, 'r') as f:
                processed = set(line.strip() for line in f if line.strip())
        
        new_files = [f for f in html_files if f.name not in processed]
        return new_files, len(processed), len(html_files)
    
    def master_modified_since_tickers(self):
        if not self.master_path.exists():
            return False
        
        master_mtime = self.get_file_mtime(self.master_path)
        ticker_files = list(self.paths['tickers'].glob('*.csv'))
        
        if not ticker_files:
            return True
        
        oldest_ticker_mtime = min(self.get_file_mtime(f) for f in ticker_files)
        return master_mtime > oldest_ticker_mtime
    
    def ticker_modified_since_enriched(self, ticker):
        ticker_path = self.paths['tickers'] / f"{ticker}.csv"
        enriched_path = self.paths['enriched'] / f"{ticker}_enriched.csv"
        
        if not ticker_path.exists():
            return False
        if not enriched_path.exists():
            return True
        
        return self.get_file_mtime(ticker_path) > self.get_file_mtime(enriched_path)

# ============================================================
# HTML PARSER
# ============================================================

class HTMLParser:
    """Parses Hedgeye Risk Range HTML files"""
    
    def __init__(self, logger):
        self.logger = logger
    
    def parse_file(self, html_path):
        try:
            html_date = self._extract_date_from_filename(html_path)
            if html_date is None:
                self.logger.error(f"  Could not parse date: {html_path.name}")
                return None
            
            df = self._extract_table_data(html_path)
            if df is None or df.empty:
                return None
            
            df['HMTL_DATE'] = html_date
            df['TREND'] = df['INDEX'].str.extract(r'\((BEARISH|BULLISH|NEUTRAL)\)')[0]
            df[['TICKER', 'NAME']] = df['INDEX'].str.split(" ", n=1, expand=True)
            
            df = df[['HMTL_DATE', 'INDEX', 'TICKER', 'BUY TRADE',
                    'SELL TRADE', 'PREV. CLOSE', 'TREND']].copy()
            df = df.drop_duplicates('INDEX')
            
            return df
            
        except Exception as e:
            self.logger.error(f"  Parsing failed: {e}")
            return None
    
    def _extract_date_from_filename(self, html_path):
        filename = html_path.stem
        
        for fmt in ["%B %d, %Y", "%B %d %Y", "%m-%d-%Y"]:
            try:
                parsed_date = datetime.strptime(filename, fmt)
                return parsed_date.strftime("%m/%d/%Y")
            except ValueError:
                continue
        return None
    
    def _extract_table_data(self, html_path):
        try:
            with open(html_path, encoding='utf-8') as f:
                tables = pd.read_html(f, attrs={'class': 'dtr-table'})
                
                if not tables:
                    self.logger.error(f"  No table found with class='dtr-table'")
                    return None
                
                df = tables[0]
                required_cols = ['INDEX', 'BUY TRADE', 'SELL TRADE', 'PREV. CLOSE']
                missing = [col for col in required_cols if col not in df.columns]
                
                if missing:
                    self.logger.error(f"  Missing columns: {missing}")
                    return None
                
                return df
                
        except Exception as e:
            self.logger.error(f"  Table extraction failed: {e}")
            return None

# ============================================================
# TICKER ENRICHER
# ============================================================

class TickerEnricher:
    """Enriches ticker data with Yahoo Finance OHLC + Volatility"""
    
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.start_date = config['enrichment']['start_date']
        self.end_date = datetime.now().strftime("%Y-%m-%d")
        self.max_retries = config['pipeline']['max_retries']
        self.ohlc_mapping = config['enrichment']['ohlc_column_mapping']
        self.vol_mapping = config['enrichment']['vol_column_mapping']
    
    def enrich_ticker(self, ticker, ticker_df):
        try:
            yahoo_ticker = self.config['enrichment']['yahoo_tickers'].get(ticker)
            if not yahoo_ticker:
                self.logger.error(f"  No Yahoo ticker mapped for {ticker}")
                return None
            
            vol_ticker = self.config['enrichment']['volatility_tickers'].get(ticker, '^VIX')
            ohlc_prefix = self.ohlc_mapping.get(ticker, ticker)
            vol_prefix = self.vol_mapping.get(ticker, 'VIX')
            
            if f'{ohlc_prefix}_Close' == f'{vol_prefix}_Close':
                self.logger.warning(f"  ⚠️  Column collision - appending '_VOL' to volatility")
                vol_prefix = f'{vol_prefix}_VOL'
            
            self.logger.info(f"  Yahoo ticker: {yahoo_ticker}")
            self.logger.info(f"  OHLC prefix: {ohlc_prefix}")
            self.logger.info(f"  Vol prefix: {vol_prefix}")
            
            ticker_df = ticker_df.copy()
            ticker_df['Date'] = pd.to_datetime(ticker_df['HMTL_DATE'], format='%m/%d/%Y')
            ticker_df = ticker_df.sort_values('Date').reset_index(drop=True)
            
            self.logger.info(f"  Downloading {yahoo_ticker} OHLC...")
            ohlc_df = self._fetch_yahoo_data(yahoo_ticker, 'OHLC', ohlc_prefix)
            if ohlc_df is None:
                return None
            
            self.logger.info(f"  Downloading {vol_ticker} volatility...")
            vol_df = self._fetch_yahoo_data(vol_ticker, 'VOL', vol_prefix)
            if vol_df is None:
                return None
            
            spine = pd.DataFrame({'Date': ohlc_df.index})
            market_df = (
                spine
                .merge(ohlc_df, left_on='Date', right_index=True, how='left')
                .merge(vol_df, left_on='Date', right_index=True, how='left')
            )
            
            merged = market_df.merge(ticker_df, on='Date', how='left')
            
            duplicate_cols = merged.columns[merged.columns.duplicated()].tolist()
            if duplicate_cols:
                self.logger.error(f"  ❌ Duplicate columns: {duplicate_cols}")
                merged = merged.loc[:, ~merged.columns.duplicated(keep='first')]
            
            original_cols = [c for c in ticker_df.columns if c != 'Date']
            missing_mask = merged[original_cols].isnull().all(axis=1)
            merged['NEEDS_MANUAL_UPDATE'] = missing_mask.map({True: 'YES', False: ''})
            
            n_missing = missing_mask.sum()
            if n_missing > 0:
                self.logger.warning(f"  ⚠️  {n_missing} trading days missing from original CSV")
            
            numeric_cols = [c for c in merged.columns
                          if c.endswith(('_Open', '_High', '_Low', '_Close'))]
            for col in numeric_cols:
                if col in merged.columns:
                    merged[col] = merged[col].round(2)
            
            training_col_order = [
                'Date', 'TICKER', 'BUY TRADE', 'SELL TRADE', 'PREV. CLOSE',
                'TREND', 'INDEX',
                f'{ohlc_prefix}_Open', f'{ohlc_prefix}_High',
                f'{ohlc_prefix}_Low', f'{ohlc_prefix}_Close',
                f'{vol_prefix}_Close',
                'NEEDS_MANUAL_UPDATE'
            ]
            
            for col in training_col_order:
                if col not in merged.columns:
                    merged[col] = ''
            
            merged = merged[training_col_order]
            merged['Date'] = merged['Date'].dt.strftime('%m/%d/%Y')
            
            self.logger.info(f"  ✓ Enrichment complete: {len(merged)} rows")
            return merged
            
        except Exception as e:
            self.logger.error(f"  Enrichment failed: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return None
    
    def _fetch_yahoo_data(self, ticker, data_type='OHLC', column_prefix=''):
        end_plus = (
            datetime.strptime(self.end_date, '%Y-%m-%d') + timedelta(days=1)
        ).strftime('%Y-%m-%d')
        
        for attempt in range(self.max_retries):
            try:
                df = yf.download(
                    ticker,
                    start=self.start_date,
                    end=end_plus,
                    auto_adjust=True,
                    progress=False
                )
                
                if df.empty:
                    raise ValueError(f"No data returned for {ticker}")
                
                df.index = pd.to_datetime(df.index).normalize()
                
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                
                if data_type == 'OHLC':
                    df = df[['Open', 'High', 'Low', 'Close']].rename(columns={
                        'Open':  f'{column_prefix}_Open',
                        'High':  f'{column_prefix}_High',
                        'Low':   f'{column_prefix}_Low',
                        'Close': f'{column_prefix}_Close',
                    })
                elif data_type == 'VOL':
                    df = df[['Close']].rename(columns={
                        'Close': f'{column_prefix}_Close'
                    })
                
                self.logger.info(
                    f"    Downloaded {len(df)} days "
                    f"({df.index.min().date()} to {df.index.max().date()})"
                )
                
                return df
                
            except Exception as e:
                if attempt < self.max_retries - 1:
                    self.logger.warning(f"    Attempt {attempt + 1} failed. Retrying...")
                    import time
                    time.sleep(2)
                else:
                    self.logger.error(f"    Failed after {self.max_retries} attempts: {e}")
                    return None
        
        return None

# ============================================================
# MAIN ETL PIPELINE
# ============================================================

def main():
    logger.info("="*70)
    logger.info("ETL PIPELINE START")
    logger.info("="*70)
    
    detector = ChangeDetector(PATHS)
    
    new_html_files, processed_count, total_html = detector.get_new_html_files()
    master_needs_propagation = detector.master_modified_since_tickers()
    
    logger.info(f"\n📋 PIPELINE PLAN:")
    logger.info(f"   HTML Files: {len(new_html_files)} new / {total_html} total")
    logger.info(f"   Master needs propagation: {master_needs_propagation}")
    
    needs_enrich = []
    for ticker in CONFIG['enrichment']['yahoo_tickers'].keys():
        if detector.ticker_modified_since_enriched(ticker):
            needs_enrich.append(ticker)
    
    if not new_html_files and not master_needs_propagation and not needs_enrich:
        logger.info("\n✅ Everything up-to-date! No processing needed.")
        return
    
    # STAGE 1: HTML PARSING
    new_csvs = []
    
    if new_html_files:
        logger.info("\n" + "="*70)
        logger.info("STAGE 1: HTML PARSING")
        logger.info("="*70)
        
        html_parser = HTMLParser(logger)
        success_count = 0
        error_count = 0
        
        for html_file in new_html_files:
            try:
                logger.info(f"\nProcessing: {html_file.name}")
                
                df = html_parser.parse_file(html_file)
                
                if df is None or df.empty:
                    logger.error(f"  ❌ No data extracted")
                    error_count += 1
                    if CONFIG['pipeline']['skip_malformed_html']:
                        continue
                    else:
                        raise ValueError(f"Failed to parse {html_file.name}")
                
                html_date = df['HMTL_DATE'].iloc[0]
                csv_filename = f"RR_{html_date.replace('/', '-')}.csv"
                csv_path = PATHS['processed'] / csv_filename
                
                df.to_csv(csv_path, index=False)
                logger.info(f"  ✅ Saved: {csv_filename} ({len(df)} rows)")
                
                new_csvs.append(csv_path)
                success_count += 1
                
                with open(detector.processed_tracker, 'a') as f:
                    f.write(html_file.name + '\n')
                
            except Exception as e:
                logger.error(f"  ❌ Error: {e}")
                error_count += 1
                if not CONFIG['pipeline']['skip_malformed_html']:
                    raise
        
        logger.info(f"\n✅ HTML parsing complete: {success_count} success, {error_count} errors")
    
    # STAGE 2: MASTER AGGREGATION
    if new_csvs:
        logger.info("\n" + "="*70)
        logger.info("STAGE 2: MASTER AGGREGATION")
        logger.info("="*70)
        
        master_path = PATHS['master'] / CONFIG['master_filename']
        
        if master_path.exists() and CONFIG['pipeline']['backup_before_merge']:
            backup_name = f"{master_path.stem}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            backup_path = PATHS['master'] / backup_name
            shutil.copy2(master_path, backup_path)
            logger.info(f"✅ Backed up master to: {backup_name}")
        
        if master_path.exists():
            master_df = pd.read_csv(master_path)
            logger.info(f"Loaded existing master: {len(master_df):,} rows")
        else:
            master_df = pd.DataFrame()
            logger.info("Creating new master CSV")
        
        new_dfs = []
        for csv_path in new_csvs:
            try:
                df = pd.read_csv(csv_path)
                new_dfs.append(df)
                logger.info(f"  Loaded: {csv_path.name} ({len(df)} rows)")
            except Exception as e:
                logger.error(f"  Failed to load {csv_path.name}: {e}")
        
        if new_dfs:
            combined_new = pd.concat(new_dfs, ignore_index=True)
            logger.info(f"Combined new data: {len(combined_new)} rows")
            
            if not master_df.empty:
                master_df = pd.concat([master_df, combined_new], ignore_index=True)
            else:
                master_df = combined_new
            
            initial_count = len(master_df)
            master_df = master_df.drop_duplicates(
                subset=['HMTL_DATE', 'TICKER'],
                keep='last'
            )
            duplicates_removed = initial_count - len(master_df)
            
            if duplicates_removed > 0:
                logger.info(f"Removed {duplicates_removed} duplicate entries")
            
            master_df['_sort_date'] = pd.to_datetime(master_df['HMTL_DATE'], format='%m/%d/%Y')
            master_df = master_df.sort_values('_sort_date')
            master_df = master_df.drop(columns=['_sort_date'])
            master_df = master_df.reset_index(drop=True)
            
            master_df.to_csv(master_path, index=False)
            logger.info(f"✅ Saved master CSV: {len(master_df):,} total rows")
            
            dates = pd.to_datetime(master_df['HMTL_DATE'], format='%m/%d/%Y')
            logger.info(f"   Date range: {dates.min().date()} to {dates.max().date()}")
    
    # STAGE 3: TICKER SUBSETTING
    if new_csvs or master_needs_propagation:
        logger.info("\n" + "="*70)
        logger.info("STAGE 3: TICKER SUBSETTING")
        logger.info("="*70)
        
        master_path = PATHS['master'] / CONFIG['master_filename']
        
        if not master_path.exists():
            logger.error("Master CSV not found - cannot create subsets")
        else:
            master_df = pd.read_csv(master_path)
            logger.info(f"Loaded master: {len(master_df):,} rows")
            
            master_df['_ticker_clean'] = master_df['TICKER'].str.strip()
            tracked = CONFIG['tracked_tickers']
            logger.info(f"Creating subsets for {len(tracked)} tickers")
            
            for ticker in tracked:
                try:
                    ticker_df = master_df[master_df['_ticker_clean'] == ticker].copy()
                    
                    if ticker_df.empty:
                        logger.warning(f"  ⚠️  {ticker}: No data found in master")
                        ticker_df = pd.DataFrame(
                            columns=[c for c in master_df.columns if c != '_ticker_clean']
                        )
                    else:
                        ticker_df = ticker_df.drop(columns=['_ticker_clean'])
                    
                    ticker_path = PATHS['tickers'] / f"{ticker}.csv"
                    ticker_df.to_csv(ticker_path, index=False)
                    
                    if not ticker_df.empty:
                        dates = pd.to_datetime(ticker_df['HMTL_DATE'], format='%m/%d/%Y')
                        date_range = f"{dates.min().date()} to {dates.max().date()}"
                        
                        if len(ticker_df) < 252:
                            logger.warning(
                                f"  ⚠️  {ticker}: {len(ticker_df)} rows (< 1 year) | {date_range}"
                            )
                        else:
                            logger.info(
                                f"  ✅ {ticker}: {len(ticker_df)} rows | {date_range}"
                            )
                    else:
                        logger.warning(f"  ⚠️  {ticker}: Created empty placeholder")
                
                except Exception as e:
                    logger.error(f"  ❌ {ticker}: Failed to create subset: {e}")
            
            logger.info(f"✅ Ticker subsetting complete")
    
    # STAGE 4: ENRICHMENT
    if CONFIG['pipeline']['auto_enrich_all']:
        logger.info("\n" + "="*70)
        logger.info("STAGE 4: ENRICHMENT")
        logger.info("="*70)
        
        enricher = TickerEnricher(CONFIG, logger)
        ticker_list = list(CONFIG['enrichment']['yahoo_tickers'].keys())
        
        logger.info(f"Enriching {len(ticker_list)} tickers")
        
        success_count = 0
        error_count = 0
        skipped_count = 0
        
        for ticker in ticker_list:
            try:
                logger.info(f"\n{'─'*70}")
                logger.info(f"Enriching: {ticker}")
                logger.info(f"{'─'*70}")
                
                ticker_path = PATHS['tickers'] / f"{ticker}.csv"
                enriched_path = PATHS['enriched'] / f"{ticker}_enriched.csv"
                
                if not ticker_path.exists():
                    logger.error(f"  ❌ Ticker file not found: {ticker}.csv")
                    error_count += 1
                    continue
                
                ticker_df = pd.read_csv(ticker_path)
                
                if ticker_df.empty:
                    logger.warning(f"  ⚠️  {ticker}.csv is empty - skipping")
                    error_count += 1
                    continue
                
                logger.info(f"  Loaded {len(ticker_df)} rows from {ticker}.csv")
                
                if enriched_path.exists():
                    ticker_mtime = ticker_path.stat().st_mtime
                    enriched_mtime = enriched_path.stat().st_mtime
                    
                    ticker_rows = len(ticker_df)
                    enriched_df_temp = pd.read_csv(enriched_path)
                    row_diff = abs(len(enriched_df_temp) - ticker_rows)
                    
                    if enriched_mtime >= ticker_mtime and row_diff < 50:
                        logger.info(f"  ✓ Enriched file up-to-date - skipping")
                        skipped_count += 1
                        continue
                    else:
                        if row_diff >= 50:
                            logger.info(
                                f"  ⚠️  Row count changed "
                                f"({len(enriched_df_temp)} → {ticker_rows}) - re-enriching"
                            )
                
                enriched_df = enricher.enrich_ticker(ticker, ticker_df)
                
                if enriched_df is None:
                    logger.error(f"  ❌ Enrichment failed")
                    error_count += 1
                    continue
                
                enriched_df.to_csv(enriched_path, index=False)
                logger.info(f"  ✅ Saved: {enriched_path.name} ({len(enriched_df)} rows)")
                
                needs_update = enriched_df['NEEDS_MANUAL_UPDATE'] == 'YES'
                if needs_update.any():
                    logger.warning(f"  ⚠️  {needs_update.sum()} rows need manual update")
                
                success_count += 1
                
            except Exception as e:
                logger.error(f"  ❌ Error enriching {ticker}: {e}")
                import traceback
                logger.debug(traceback.format_exc())
                error_count += 1
        
        logger.info(f"\n{'='*70}")
        logger.info(f"✅ Enrichment complete:")
        logger.info(f"   Success: {success_count}")
        logger.info(f"   Skipped (up-to-date): {skipped_count}")
        logger.info(f"   Errors:  {error_count}")
        logger.info(f"{'='*70}")
    
    logger.info("\n" + "="*70)
    logger.info("✅ PIPELINE COMPLETE")
    logger.info("="*70)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        exit(1)
