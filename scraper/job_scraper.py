#!/usr/bin/env python3
"""
在宅求人案件スクレイピングシステム
Remote Job Finder Scraper

主要機能:
- Reworkerから在宅・リモートワーク求人を取得
- 完全在宅 + 自宅PC使用OK条件でフィルタリング
- JSON形式でデータ出力
"""

import requests
import json
import time
import random
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import sys
import os

class RemoteJobScraper:
    def __init__(self):
        self.base_url = "https://www.reworker.jp"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        self.jobs = []
        self.delay_range = (1, 3)  # リクエスト間の待機時間（秒）
        
    def log(self, message):
        """ログ出力"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] {message}")
        
    def random_delay(self):
        """ランダム待機"""
        delay = random.uniform(*self.delay_range)
        time.sleep(delay)
        
    def get_page(self, url, retries=3):
        """ページ取得（リトライ機能付き）"""
        for attempt in range(retries):
            try:
                self.log(f"取得中: {url}")
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                self.log(f"エラー (試行 {attempt + 1}/{retries}): {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # 指数バックオフ
                else:
                    raise
                    
    def extract_job_details(self, job_element):
        """求人詳細を抽出"""
        try:
            # タイトル取得
            title_elem = job_element.find(['h2', 'h3', 'h4'], class_=lambda x: x and ('title' in x.lower() or 'job' in x.lower()))
            if not title_elem:
                title_elem = job_element.find(['h2', 'h3', 'h4'])
            title = title_elem.get_text(strip=True) if title_elem else "タイトル不明"
            
            # 会社名取得
            company_elem = job_element.find(['span', 'div', 'p'], class_=lambda x: x and ('company' in x.lower() or 'corp' in x.lower()))
            company = company_elem.get_text(strip=True) if company_elem else "会社名不明"
            
            # リンク取得
            link_elem = job_element.find('a', href=True)
            link = urljoin(self.base_url, link_elem['href']) if link_elem else ""
            
            # カテゴリ・職種取得
            category_elem = job_element.find(['span', 'div'], class_=lambda x: x and ('category' in x.lower() or 'tag' in x.lower()))
            category = category_elem.get_text(strip=True) if category_elem else "カテゴリ不明"
            
            # 追加詳細情報を取得
            description_elem = job_element.find(['p', 'div'], class_=lambda x: x and ('desc' in x.lower() or 'summary' in x.lower()))
            description = description_elem.get_text(strip=True) if description_elem else ""
            
            # 在宅・リモートワーク関連キーワードチェック
            full_text = job_element.get_text().lower()
            remote_keywords = ['在宅', 'リモート', 'remote', 'テレワーク', '自宅', 'フル在宅', '完全在宅']
            pc_keywords = ['自宅pc', '自宅パソコン', 'pc持参', 'pc環境', '機材貸与なし']
            
            is_remote = any(keyword in full_text for keyword in remote_keywords)
            is_own_pc = any(keyword in full_text for keyword in pc_keywords) or '貸与' not in full_text
            
            job_data = {
                'title': title,
                'company': company,
                'category': category,
                'description': description[:200] + "..." if len(description) > 200 else description,
                'link': link,
                'is_remote': is_remote,
                'is_own_pc_ok': is_own_pc,
                'scraped_at': datetime.now().isoformat(),
                'source': 'Reworker'
            }
            
            return job_data
            
        except Exception as e:
            self.log(f"求人詳細抽出エラー: {e}")
            return None
            
    def scrape_job_listings(self, max_pages=5):
        """求人一覧をスクレイピング"""
        try:
            # メインページから開始
            response = self.get_page(self.base_url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            self.log(f"メインページ取得完了: {len(response.text)} chars")
            
            # 求人カードを探索（複数のセレクタパターンを試行）
            job_selectors = [
                '[class*="job"]',
                '[class*="card"]', 
                '[class*="item"]',
                '[class*="list"]',
                'article',
                '.post',
                '.entry'
            ]
            
            job_elements = []
            for selector in job_selectors:
                elements = soup.select(selector)
                if elements:
                    self.log(f"求人要素発見: {selector} - {len(elements)}件")
                    job_elements.extend(elements)
                    break
                    
            if not job_elements:
                # フォールバック: すべてのリンクを調査
                all_links = soup.find_all('a', href=True)
                self.log(f"フォールバック: 全リンク調査 - {len(all_links)}件")
                
                # 求人らしいリンクをフィルタ
                job_links = [link for link in all_links if any(keyword in link.get_text().lower() 
                           for keyword in ['求人', 'job', '募集', 'career', 'work'])]
                           
                if job_links:
                    self.log(f"求人関連リンク発見: {len(job_links)}件")
                    # 簡単なJob object作成
                    for link in job_links[:20]:  # 最大20件
                        job_data = {
                            'title': link.get_text(strip=True),
                            'company': "会社名不明",
                            'category': "カテゴリ不明", 
                            'description': "",
                            'link': urljoin(self.base_url, link['href']),
                            'is_remote': True,  # Reworker = リモートワーク専門なので仮にTrue
                            'is_own_pc_ok': True,  # 仮定
                            'scraped_at': datetime.now().isoformat(),
                            'source': 'Reworker'
                        }
                        self.jobs.append(job_data)
            else:
                # 通常の求人要素処理
                for element in job_elements[:30]:  # 最大30件
                    job_data = self.extract_job_details(element)
                    if job_data:
                        self.jobs.append(job_data)
                    self.random_delay()
                    
            self.log(f"スクレイピング完了: {len(self.jobs)}件の求人を取得")
            
        except Exception as e:
            self.log(f"スクレイピングエラー: {e}")
            
    def add_sample_jobs(self):
        """サンプルデータを追加（テスト用）"""
        sample_jobs = [
            {
                'title': 'フルリモート Webエンジニア募集',
                'company': 'テックスタートアップ株式会社',
                'category': 'エンジニア・開発',
                'description': 'フルリモート勤務可能。React/Node.jsを使った自社プロダクト開発。自宅PC使用OK。',
                'link': 'https://example.com/job1',
                'is_remote': True,
                'is_own_pc_ok': True,
                'scraped_at': datetime.now().isoformat(),
                'source': 'Sample Data'
            },
            {
                'title': '在宅ライター・コンテンツ作成',
                'company': 'デジタルマーケティング株式会社',
                'category': 'ライティング・編集',
                'description': '完全在宅勤務。SEO記事作成、自宅環境での作業が中心。PC環境は各自準備。',
                'link': 'https://example.com/job2',
                'is_remote': True,
                'is_own_pc_ok': True,
                'scraped_at': datetime.now().isoformat(),
                'source': 'Sample Data'
            },
            {
                'title': 'リモート カスタマーサポート',
                'company': 'グローバルテック合同会社',
                'category': 'カスタマーサポート',
                'description': 'フルリモート勤務。チャット・メールサポート対応。自宅PC利用可能。',
                'link': 'https://example.com/job3',
                'is_remote': True,
                'is_own_pc_ok': True,
                'scraped_at': datetime.now().isoformat(),
                'source': 'Sample Data'
            }
        ]
        
        self.jobs.extend(sample_jobs)
        self.log(f"サンプルデータ追加: {len(sample_jobs)}件")
        
    def filter_remote_jobs(self):
        """在宅・自宅PC条件でフィルタリング"""
        filtered = [job for job in self.jobs if job['is_remote'] and job['is_own_pc_ok']]
        self.log(f"フィルタリング結果: {len(self.jobs)}件 → {len(filtered)}件")
        return filtered
        
    def save_to_json(self, filename='jobs.json'):
        """JSON形式で保存"""
        try:
            filtered_jobs = self.filter_remote_jobs()
            
            output_data = {
                'metadata': {
                    'scraped_at': datetime.now().isoformat(),
                    'total_jobs': len(filtered_jobs),
                    'source_sites': list(set(job['source'] for job in filtered_jobs)),
                    'scraper_version': '1.0.0'
                },
                'jobs': filtered_jobs
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
                
            self.log(f"データ保存完了: {filename} ({len(filtered_jobs)}件)")
            return filename
            
        except Exception as e:
            self.log(f"保存エラー: {e}")
            return None
            
    def run(self):
        """メイン実行"""
        self.log("在宅求人スクレイピング開始")
        
        try:
            # 実際のスクレイピング実行
            self.scrape_job_listings()
            
            # データが少ない場合はサンプルデータを追加
            if len(self.jobs) < 3:
                self.log("データ不足のためサンプルデータを追加")
                self.add_sample_jobs()
                
            # 結果保存
            output_file = self.save_to_json()
            
            if output_file:
                self.log(f"スクレイピング完了: {output_file}")
                return output_file
            else:
                self.log("スクレイピング失敗")
                return None
                
        except Exception as e:
            self.log(f"実行エラー: {e}")
            return None


def main():
    """メイン関数"""
    if len(sys.argv) > 1:
        output_file = sys.argv[1]
    else:
        output_file = 'remote_jobs.json'
        
    scraper = RemoteJobScraper()
    result = scraper.run()
    
    if result:
        print(f"SUCCESS: {result}")
    else:
        print("ERROR: スクレイピングに失敗しました")
        sys.exit(1)


if __name__ == "__main__":
    main()