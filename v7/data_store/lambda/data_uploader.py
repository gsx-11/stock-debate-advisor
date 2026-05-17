"""
Data Uploader Lambda - Automatically uploads stock data from data_store to DynamoDB
Triggered on CDK deployment via custom resource
"""

import json
import os
import sys
import boto3
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for uploading data to DynamoDB
    Expected event from CDK custom resource:
    {
        "companies_table": "companies",
        "financial_reports_table": "financial_reports",
        "ohlc_prices_table": "ohlc_prices",
        "data_path": "/tmp/data"
    }
    """
    try:
        logger.info(f"Event: {json.dumps(event)}")
        
        # Get table names from environment or event
        companies_table_name = os.environ.get('COMPANIES_TABLE', 'companies')
        financial_table_name = os.environ.get('FINANCIAL_REPORTS_TABLE', 'financial_reports')
        ohlc_table_name = os.environ.get('OHLC_PRICES_TABLE', 'ohlc_prices')
        
        # Initialize DynamoDB tables
        companies_table = dynamodb.Table(companies_table_name)
        financial_table = dynamodb.Table(financial_table_name)
        ohlc_table = dynamodb.Table(ohlc_table_name)
        
        # Data path - in Lambda, data will be in /tmp/data (copied during deployment)
        data_path = Path('/tmp/data')
        
        # Check if data exists in Lambda environment
        if not data_path.exists():
            # For local development or if data not bundled
            data_path = Path(__file__).parent.parent / 'data'
            
        if not data_path.exists():
            logger.warning(f"Data path not found: {data_path}")
            return success_response({
                'status': 'warning',
                'message': f'Data path not found at {data_path}',
                'items_uploaded': 0
            })
        
        # Upload data
        stats = upload_all_data(data_path, companies_table, financial_table, ohlc_table)
        
        logger.info(f"Upload completed: {stats}")
        return success_response({
            'status': 'success',
            'message': 'Data upload completed',
            **stats
        })
        
    except Exception as e:
        logger.error(f"Error uploading data: {str(e)}", exc_info=True)
        return error_response(str(e))


def upload_all_data(
    data_path: Path,
    companies_table,
    financial_table,
    ohlc_table
) -> Dict[str, int]:
    """
    Upload all stock data from data_path to DynamoDB tables
    Data structure: data/YYYY/TICKER/[company_info.json, financial_reports.json, ohlc_prices.json]
    """
    stats = {
        'companies_uploaded': 0,
        'financial_reports_uploaded': 0,
        'ohlc_prices_uploaded': 0,
        'errors': []
    }
    
    # Find all ticker directories
    for year_dir in data_path.iterdir():
        if not year_dir.is_dir():
            continue
            
        logger.info(f"Processing year: {year_dir.name}")
        
        for ticker_dir in year_dir.iterdir():
            if not ticker_dir.is_dir():
                continue
                
            ticker = ticker_dir.name.replace('.VN', '')
            
            try:
                # Load and upload company info
                company_file = ticker_dir / 'company_info.json'
                if company_file.exists():
                    with open(company_file, 'r') as f:
                        company_data = json.load(f)
                        upload_company(companies_table, company_data, ticker)
                        stats['companies_uploaded'] += 1
                        logger.info(f"Uploaded company info for {ticker}")
                
                # Load and upload financial reports
                financial_file = ticker_dir / 'financial_reports.json'
                if financial_file.exists():
                    with open(financial_file, 'r') as f:
                        financial_data = json.load(f)
                        count = upload_financial_reports(financial_table, financial_data, ticker)
                        stats['financial_reports_uploaded'] += count
                        logger.info(f"Uploaded {count} financial reports for {ticker}")
                
                # Load and upload OHLC prices
                ohlc_file = ticker_dir / 'ohlc_prices.json'
                if ohlc_file.exists():
                    with open(ohlc_file, 'r') as f:
                        ohlc_data = json.load(f)
                        count = upload_ohlc_prices(ohlc_table, ohlc_data, ticker)
                        stats['ohlc_prices_uploaded'] += count
                        logger.info(f"Uploaded {count} OHLC records for {ticker}")
                
            except Exception as e:
                error_msg = f"Error processing {ticker}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                stats['errors'].append(error_msg)
    
    return stats


def upload_company(table, company_data: Dict[str, Any], ticker: str) -> None:
    """Upload company metadata to companies table"""
    if not ticker or not isinstance(ticker, str):
        raise ValueError(f"Invalid ticker: {ticker}")

    info = company_data.get('info', {})
    description = info.get('description', '') or ''

    item = {
        'ticker': ticker,
        'symbol': company_data.get('symbol', ticker),
        'timestamp': company_data.get('timestamp', datetime.utcnow().isoformat()),
        'name': info.get('name', ''),
        'sector': info.get('sector', ''),
        'industry': info.get('industry', ''),
        'market_cap': info.get('market_cap', 0),
        'website': info.get('website', ''),
        'description': description[:500],
        'exchange': info.get('exchange', ''),
        'currency': info.get('currency', 'VND'),
        'updated_at': datetime.utcnow().isoformat()
    }
    
    table.put_item(Item=item)


def upload_financial_reports(table, financial_data: Dict[str, Any], ticker: str) -> int:
    """Upload financial reports to financial_reports table"""
    if not ticker or not isinstance(ticker, str):
        raise ValueError(f"Invalid ticker: {ticker}")

    count = 0
    
    # Handle both list and dict formats
    reports = financial_data.get('reports', [])
    if isinstance(reports, dict):
        reports = [reports]
    elif not isinstance(reports, list):
        reports = [financial_data]
    
    for report in reports:
        try:
            timestamp = report.get('timestamp', datetime.utcnow().isoformat())
            metrics = report.get('metrics', {})

            def safe_float(val: Any, default: float = 0.0) -> float:
                try:
                    return float(val) if val is not None else default
                except (TypeError, ValueError):
                    return default
            
            item = {
                'ticker': ticker,
                'timestamp': timestamp,
                'pe_ratio': safe_float(metrics.get('pe_ratio')),
                'pb_ratio': safe_float(metrics.get('pb_ratio')),
                'dividend_yield': safe_float(metrics.get('dividend_yield')),
                'eps': safe_float(metrics.get('eps')),
                'roe': safe_float(metrics.get('roe')),
                'roa': safe_float(metrics.get('roa')),
                'debt_to_equity': safe_float(metrics.get('debt_to_equity')),
                'current_ratio': safe_float(metrics.get('current_ratio')),
                'revenue': safe_float(metrics.get('revenue')),
                'net_income': safe_float(metrics.get('net_income')),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            table.put_item(Item=item)
            count += 1
        except Exception as e:
            logger.warning(f"Error uploading financial report for {ticker}: {str(e)}")
    
    return count


def upload_ohlc_prices(table, ohlc_data: Dict[str, Any], ticker: str) -> int:
    """Upload OHLC prices to ohlc_prices table"""
    if not ticker or not isinstance(ticker, str):
        raise ValueError(f"Invalid ticker: {ticker}")

    count = 0
    
    # Handle both list and dict formats
    prices = ohlc_data.get('prices', [])
    if isinstance(prices, dict):
        prices = [prices]
    elif not isinstance(prices, list):
        prices = [ohlc_data]
    
    for price_record in prices:
        try:
            date = price_record.get('date', price_record.get('timestamp', datetime.utcnow().isoformat()))
            if not date:
                logger.warning(f"Skipping OHLC record for {ticker}: missing date")
                continue

            def safe_float(val: Any, default: float = 0.0) -> float:
                try:
                    return float(val) if val is not None else default
                except (TypeError, ValueError):
                    return default

            close_price = safe_float(price_record.get('close'))

            item = {
                'ticker': ticker,
                'date': date,
                'open': safe_float(price_record.get('open')),
                'high': safe_float(price_record.get('high')),
                'low': safe_float(price_record.get('low')),
                'close': close_price,
                'volume': int(safe_float(price_record.get('volume'))),
                'adjusted_close': safe_float(price_record.get('adjusted_close', close_price)),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            table.put_item(Item=item)
            count += 1
        except Exception as e:
            logger.warning(f"Error uploading OHLC record for {ticker}: {str(e)}")
    
    return count


def success_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return success response"""
    return {
        'statusCode': 200,
        'body': json.dumps(data)
    }


def error_response(error: str) -> Dict[str, Any]:
    """Return error response"""
    return {
        'statusCode': 500,
        'body': json.dumps({'error': error})
    }
