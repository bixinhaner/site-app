#!/usr/bin/env python3
"""
Daily Sales Report Generator
This script generates a daily sales report with mock data and integrates with the project's email system.
"""

import random
import json
import os
import sys
import yaml
from datetime import datetime, timedelta

# Add parent directory to path to import project modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from direct_email_service import DirectEmailService
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

def generate_daily_sales_report():
    """Generate a daily sales report with mock data"""
    # Get the project root directory (parent of reports directory)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Load global configuration
    config_path = os.path.join(project_root, 'config.yaml')
    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            global_config = yaml.safe_load(file)
    except FileNotFoundError:
        print("Error: config.yaml not found")
        return "Error: Global configuration file not found"
    
    # Extract daily_sales configuration from global config
    reports = global_config.get('reports', [])
    daily_sales_report = None
    
    # Find the daily_sales report configuration
    for report in reports:
        if 'daily_sales' in report.get('script_path', '') or report.get('name') == 'test':
            daily_sales_report = report
            break
    
    if not daily_sales_report:
        print("Error: daily_sales report configuration not found in global config")
        return "Error: Report configuration not found"
    
    # Get the daily_sales specific configuration
    config = daily_sales_report.get('daily_sales_config', {})
    
    # Generate mock data
    cities = config.get('cities', ['CENTRAL', 'COPPERBELT', 'EASTERN', 'LUSAKA', 'NORTHERN', 'NORTHWESTERN', 'SOUTHERN', 'WESTERN'])
    city_data = {}
    total_cells = 0
    
    for city in cities:
        # Generate random cell count (0-5 for most cities, 0-10 for LUSAKA)
        max_cells = 10 if city == 'LUSAKA' else 5
        cell_count = random.randint(0, max_cells)
        city_data[city] = cell_count
        total_cells += cell_count
    
    # Generate HTML report
    current_time = datetime.now().strftime("%B %d, %Y %H:%M:%S")
    report_title = config.get('report_config', {}).get('report_title', 'Daily Zero Traffic Cell Report')
    report_note = config.get('report_config', {}).get('report_note', 'Note: the statistical duration is 16 hours per day exclude 0:00 to 8:00 with low traffic period.')
    
    html_content = f"""<!DOCTYPE html>
<html lang='en'>
<head>
    <meta charset='UTF-8'>
    <meta name='viewport' content='width=device-width, initial-scale=1.0'>
    <title>{report_title}</title>
</head>
<body style='font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: #f4f7f6;'>
    <table style='width: 100%; max-width: 800px; margin: 20px auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);' cellpadding='0' cellspacing='0'>
        <!-- Header -->
        <tr>
            <td style='background-color: #004a99; color: #ffffff; padding: 30px; border-top-left-radius: 8px; border-top-right-radius: 8px; text-align: center;'>
                <h1 style='margin: 0; font-size: 28px; font-weight: bold;'>{report_title}</h1>
                <p style='margin: 5px 0 0; font-size: 16px; opacity: 0.9;'>Generated on: {current_time}</p>
            </td>
        </tr>
        <!-- City Overview Section -->
        <tr>
            <td style='padding: 25px 30px;'>
                <h2 style='font-size: 22px; color: #333; margin-top: 0; margin-bottom: 20px; border-bottom: 2px solid #004a99; padding-bottom: 10px;'>City Overview</h2>
                <div style='font-size: 0;'>
                    <div style='display: block; width: 98%; margin: 1%; background-color: #004a99; border-radius: 8px; padding: 25px; box-sizing: border-box; text-align: center; color: #ffffff;'>
                        <p style='font-size: 18px; color: #ffffff; margin: 0 0 10px; opacity: 0.9;'>Total Zero Traffic Cells</p>
                        <p style='font-size: 36px; font-weight: bold; color: #ffffff; margin: 0;'>{total_cells}</p>
                    </div>"""
    
    # Add city cards
    for city, count in city_data.items():
        html_content += f"""<div style='display: inline-block; width: 48%; margin: 1%; background-color: #f8f9fa; border-radius: 8px; padding: 20px; box-sizing: border-box; text-align: center; vertical-align: top;'>
                        <p style='font-size: 16px; color: #555; margin: 0 0 10px;'>{city} Cells</p>
                        <p style='font-size: 32px; font-weight: bold; color: #004a99; margin: 0;'>{count}</p>
                    </div>"""
    
    html_content += f"""
                </div>
            </td>
        </tr>
        <!-- Summary Section -->
        <tr>
            <td style='padding: 25px 30px;'>
                <h2 style='font-size: 22px; color: #333; margin-top: 0; margin-bottom: 20px; border-bottom: 2px solid #004a99; padding-bottom: 10px;'>Summary</h2>
                <p style='color: #555; line-height: 1.6;'>{report_note}</p>
                <div style='background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin-top: 20px;'>
                    <h3 style='color: #333; margin-top: 0;'>Key Statistics:</h3>
                    <ul style='color: #555;'>
                        <li>Total cities monitored: {len(cities)}</li>
                        <li>Total zero traffic cells: {total_cells}</li>
                        <li>Average cells per city: {total_cells / len(cities):.1f}</li>
                        <li>Report generated: {current_time}</li>
                    </ul>
                </div>
            </td>
        </tr>
        <!-- Footer -->
        <tr>
            <td style='text-align: center; padding: 20px; font-size: 12px; color: #888;'>
                <p>This is an automated report generated by the Report Scheduling Tool</p>
                <p>For questions or issues, please contact the system administrator</p>
            </td>
        </tr>
    </table>
</body>
</html>"""
    
    return html_content

def send_report_via_email():
    """Send the report via email using the project's email system"""
    if not EMAIL_AVAILABLE:
        print("Email service not available. Report generated but not sent.")
        return False
    
    try:
        # Generate the report
        report_content = generate_daily_sales_report()
        
        # Initialize email service (loads email config from email_config.yaml)
        email_service = DirectEmailService()
        
        # Test connection first
        if not email_service.test_connection():
            print("Error: Email connection failed")
            return False
        
        # Load global config to get subscribers and subject
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_file = os.path.join(project_root, 'config.yaml')
        
        subscribers = []
        subject = "Daily Zero Traffic Cell Report"
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                
                # Get subscribers from config
                for report_config in config.get('reports', []):
                    if 'daily_sales' in report_config.get('script_path', '') or report_config.get('name') == 'test':
                        subscribers = report_config.get('subscribers', [])
                        subject = report_config.get('subject', 'Daily Zero Traffic Cell Report')
                        break
            except Exception as e:
                print(f"Warning: Could not load global config: {e}")
        
        # Fallback to default if not found in config
        if not subscribers:
            subscribers = [
                {'email': 'jiangyunfeng@baicells.com', 'name': 'Jason'},
            ]
            subject = "Daily Zero Traffic Cell Report"
        
        # Send the report
        success = email_service.send_report_to_subscribers(
            report_name='daily_sales_report',
            report_content=report_content,
            subscribers=subscribers,
            subject=subject
        )
        
        if success:
            print("[SUCCESS] Report sent successfully via email!")
            return True
        else:
            print("[ERROR] Failed to send report via email")
            return False
            
    except Exception as e:
        print(f"[ERROR] Error sending report: {e}")
        return False

if __name__ == "__main__":
    # Set UTF-8 encoding for Windows compatibility
    if sys.platform.startswith('win'):
        import codecs
        try:
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
            sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())
        except:
            # If encoding setup fails, continue without it
            pass
    
    try:
        send_report_via_email()
    except UnicodeEncodeError as e:
        print(f"[ERROR] Encoding error: {e}")
        print("[INFO] This might be due to Unicode characters in the output")
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
