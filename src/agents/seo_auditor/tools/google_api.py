import os
from typing import List, Dict, Any
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest,
    Dimension,
    Metric,
    OrderBy,
    DateRange
)
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

class GoogleSEOClient:
    def __init__(self):
        self.ga4_property_id = os.getenv("GA4_PROPERTY_ID")
        self.gsc_site_url = os.getenv("GSC_SITE_URL")
        
        # Используем OAuth 2.0 данные из .env
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
        
        if not all([client_id, client_secret, refresh_token]):
            raise ValueError("Missing GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET or GOOGLE_REFRESH_TOKEN in .env")
            
        self.credentials = Credentials(
            token=None, # Access token будет получен автоматически через refresh_token
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri="https://oauth2.googleapis.com/token"
        )

    def get_high_bounce_pages(self) -> List[Dict[str, Any]]:
        """
        Fetches URLs from GA4 that have high bounce rates or very low average session duration.
        """
        print(f"Fetching high bounce pages from GA4 (Property: {self.ga4_property_id})...")
        client = BetaAnalyticsDataClient(credentials=self.credentials)
        
        request = RunReportRequest(
            property=f"properties/{self.ga4_property_id}",
            dimensions=[Dimension(name="pagePath")],
            metrics=[Metric(name="bounceRate"), Metric(name="averageSessionDuration")],
            date_ranges=[DateRange(start_date="30daysAgo", end_date="today")],
            order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="bounceRate"), desc=True)],
            limit=10
        )
        
        response = client.run_report(request)
        
        results = []
        for row in response.rows:
            results.append({
                "url": row.dimension_values[0].value,
                "bounce_rate": row.metric_values[0].value,
                "avg_duration": row.metric_values[1].value
            })
            
        return results

    def get_top_queries_for_url(self, url: str) -> List[str]:
        """
        Fetches the top search queries for a specific URL from Google Search Console.
        """
        print(f"Fetching top queries for {url} from GSC...")
        service = build('searchconsole', 'v1', credentials=self.credentials)
        
        request = {
            'startDate': '2026-01-01', 
            'endDate': '2026-05-31',
            'dimensions': ['query'],
            'dimensionFilterGroups': [{
                'filters': [{
                    'dimension': 'page',
                    'operator': 'equals',
                    'expression': url
                }]
            }],
            'rowLimit': 10
        }
        
        response = service.searchanalytics().query(siteUrl=self.gsc_site_url, body=request).execute()
        
        if 'rows' not in response:
            return []
            
        return [row['keys'][0] for row in response['rows']]

    def get_page_speed_metrics(self, url: str, device: str = "desktop") -> Dict[str, Any]:
        """
        Fetches PageSpeed Insights metrics for a given URL and device.
        """
        print(f"Fetching PageSpeed metrics for {url} ({device})...")
        api_key = os.getenv("GOOGLE_API_KEY")
        import httpx
        
        url_api = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&key={api_key}&strategy={device}"
        
        try:
            response = httpx.get(url_api)
            data = response.json()
            lighthouse = data['lighthouseResult']['categories']
            return {
                "performance": lighthouse['performance']['score'],
                "accessibility": lighthouse['accessibility']['score'],
                "best_practices": lighthouse['best_practices']['score'],
                "seo": lighthouse['seo']['score'],
            }
        except Exception as e:
            print(f"PageSpeed API error: {e}")
            return {"error": str(e)}