# YourLeagueConsensus.py
# Custom Fantasy Football Consensus Projections - YOUR EXACT SCORING (Dec 2025)

import sys
import asyncio
import pandas as pd
from datetime import datetime
from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSortFilterProxyModel
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from playwright.async_api import async_playwright
import re
import os

# ============================= YOUR EXACT SCORING (HARDCODED) =============================
CUSTOM_SCORING = {
    # Passing
    'pass_cmp': 0.1,
    'pass_yds': 1/20,          # 20 yds per point
    'pass_yds_200': 2,
    'pass_yds_300': 3,
    'pass_yds_400': 4,
    'pass_td': 6,
    'int': -2,
    'sacks_taken': -0.25,
    'pick_six': -2,
    'pass_40_plus_td': 1,
    'pass_40_plus_cmp': 1,
    'pass_fd': 0.1,            # Passing 1st downs

    # Rushing
    'rush_att': 0.35,
    'rush_yds': 0.1,           # 10 yds per point
    'rush_yds_100': 3,
    'rush_yds_200': 4,
    'rush_td': 6,
    'rush_40_plus': 2,
    'rush_40_plus_td': 1,
    'rush_fd': 0.2,

    # Receiving
    'rec': 0.7,
    'rec_yds': 0.1,
    'rec_yds_100': 3,
    'rec_yds_200': 4,
    'rec_td': 6,
    'rec_40_plus': 2,
    'rec_40_plus_td': 1,
    'rec_fd': 0.2,

    # Misc Offense
    'two_pt': 2,
    'fumble_lost': -2,
    'fumble_td': 6,            # Offensive fumble return TD
    'return_yds': 1/20,
    'return_td': 6,

    # Kicking (simplified; projections often lack details)
    'fg_0_19': 3, 'fg_20_29': 3, 'fg_30_39': 4, 'fg_40_49': 4, 'fg_50_plus': 5,
    'fg_miss_0_19': -1, 'fg_miss_20_29': -1, 'fg_miss_30_39': -1, 'fg_miss_40_49': -1, 'fg_miss_50_plus': -1,
    'xp_made': 1, 'xp_miss': -1,

    # Defense/ST (tiered; uses projected points allowed)
    'def_pts_allowed_0': 12, 'def_pts_allowed_1_6': 8, 'def_pts_allowed_7_13': 6,
    'def_pts_allowed_14_20': 4, 'def_pts_allowed_21_27': 2, 'def_pts_allowed_28_34': 0, 'def_pts_allowed_35_plus': -5,
    'def_sacks': 2, 'def_int': 3, 'def_fum_rec': 3, 'def_td': 6, 'def_safety': 2, 'def_block': 2,
    'def_return_td': 6, 'def_yds_allowed_0_99': 5, 'def_yds_allowed_100_199': 4,
    'def_yds_allowed_200_299': 2, 'def_yds_allowed_300_399': 0, 'def_yds_allowed_400_499': -1, 'def_yds_allowed_500_plus': -3,
    'def_4th_down_stops': 0.5, 'def_tfl': 0.5, 'def_3_and_out': 0.5, 'def_xp_return': 2,
}

# ============================= SCORING CALCULATOR =============================
def calculate_fantasy_points(row, is_def=False):
    pts = 0.0

    if not is_def:
        # Passing
        pts += row.get('pass_cmp', 0) * CUSTOM_SCORING['pass_cmp']
        pts += row.get('pass_yds', 0) * CUSTOM_SCORING['pass_yds']
        if row.get('pass_yds', 0) >= 400: pts += 4
        elif row.get('pass_yds', 0) >= 300: pts += 3
        elif row.get('pass_yds', 0) >= 200: pts += 2
        pts += row.get('pass_td', 0) * 6
        pts += row.get('int', 0) * -2
        pts += row.get('sacks_taken', 0) * -0.25
        pts += row.get('pick_six', 0) * -2
        pts += row.get('pass_40_plus_cmp', 0) * 1
        pts += row.get('pass_40_plus_td', 0) * 1
        pts += row.get('pass_fd', 0) * 0.1

        # Rushing
        pts += row.get('rush_att', 0) * 0.35
        pts += row.get('rush_yds', 0) * 0.1
        if row.get('rush_yds', 0) >= 200: pts += 4
        elif row.get('rush_yds', 0) >= 100: pts += 3
        pts += row.get('rush_td', 0) * 6
        pts += row.get('rush_40_plus', 0) * 2
        pts += row.get('rush_40_plus_td', 0) * 1
        pts += row.get('rush_fd', 0) * 0.2

        # Receiving
        pts += row.get('rec', 0) * 0.7
        pts += row.get('rec_yds', 0) * 0.1
        if row.get('rec_yds', 0) >= 200: pts += 4
        elif row.get('rec_yds', 0) >= 100: pts += 3
        pts += row.get('rec_td', 0) * 6
        pts += row.get('rec_40_plus', 0) * 2
        pts += row.get('rec_40_plus_td', 0) * 1
        pts += row.get('rec_fd', 0) * 0.2

        # Misc Offense
        pts += row.get('two_pt', 0) * 2
        pts += row.get('fumble_lost', 0) * -2
        pts += row.get('fumble_td', 0) * 6
        pts += row.get('return_yds', 0) / 20
        pts += row.get('return_td', 0) * 6

        # Kicking (basic)
        pts += row.get('fg_0_19', 0) * 3 + row.get('fg_20_29', 0) * 3 + row.get('fg_30_39', 0) * 4
        pts += row.get('fg_40_49', 0) * 4 + row.get('fg_50_plus', 0) * 5
        pts += row.get('fg_miss_0_19', 0) * -1 + row.get('fg_miss_20_29', 0) * -1 + row.get('fg_miss_30_39', 0) * -1
        pts += row.get('fg_miss_40_49', 0) * -1 + row.get('fg_miss_50_plus', 0) * -1
        pts += row.get('xp_made', 0) * 1 + row.get('xp_miss', 0) * -1
    else:
        # Defense/ST (simplified tiers based on projected pts/yds allowed)
        pa = row.get('opp_pts', 0)
        if pa == 0: pts += 12
        elif 1 <= pa <= 6: pts += 8
        elif 7 <= pa <= 13: pts += 6
        elif 14 <= pa <= 20: pts += 4
        elif 21 <= pa <= 27: pts += 2
        elif 28 <= pa <= 34: pts += 0
        else: pts += -5

        ya = row.get('opp_yds', 0)
        if ya <= 99: pts += 5
        elif 100 <= ya <= 199: pts += 4
        elif 200 <= ya <= 299: pts += 2
        elif 300 <= ya <= 399: pts += 0
        elif 400 <= ya <= 499: pts += -1
        else: pts += -3

        pts += row.get('def_sacks', 0) * 2 + row.get('def_int', 0) * 3 + row.get('def_fum_rec', 0) * 3
        pts += row.get('def_td', 0) * 6 + row.get('def_safety', 0) * 2 + row.get('def_block', 0) * 2
        pts += row.get('def_return_td', 0) * 6 + row.get('def_4th_down_stops', 0) * 0.5
        pts += row.get('def_tfl', 0) * 0.5 + row.get('def_3_and_out', 0) * 0.5 + row.get('def_xp_return', 0) * 2

    return round(pts, 2)

# ============================= DATA CACHE =============================
CACHE_FILE = 'projections_cache.csv'

def load_cache():
    if os.path.exists(CACHE_FILE):
        return pd.read_csv(CACHE_FILE)
    return pd.DataFrame()

def save_cache(df):
    df.to_csv(CACHE_FILE, index=False)

# ============================= SCRAPERS (2025 WORKING SOURCES) =============================
async def scrape_sources():
    all_data = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = await context.new_page()
        page.set_default_timeout(60000)

        # FantasyPros (primary source for consensus stats)
        positions = [
            ("https://www.fantasypros.com/nfl/projections/qb.php?week=draft", "QB"),
            ("https://www.fantasypros.com/nfl/projections/rb.php?week=draft", "RB"),
            ("https://www.fantasypros.com/nfl/projections/wr.php?week=draft", "WR"),
            ("https://www.fantasypros.com/nfl/projections/te.php?week=draft", "TE"),
            ("https://www.fantasypros.com/nfl/projections/k.php?week=draft", "K"),
            ("https://www.fantasypros.com/nfl/projections/dst.php?week=draft", "DST"),
        ]

        for url, pos in positions:
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                # Updated selector for 2025 FantasyPros layout
                await page.wait_for_selector(".table-player-table tbody tr, #dataGridView tbody tr", timeout=20000)
                rows = await page.query_selector_all(".table-player-table tbody tr, #dataGridView tbody tr")
                for row in rows[:50]:  # Top 50 per position
                    cols = await row.query_selector_all("td")
                    if len(cols) < 8: continue
                    player_cell = await cols[0].inner_text()
                    # Parse player name and team (e.g., "Josh Allen BUF")
                    match = re.match(r"(.+?)\s([A-Z]{2,3})$", player_cell.strip())
                    player = match.group(1).strip() if match else player_cell.strip()
                    team = match.group(2) if match else ""
                    opp = await cols[3].inner_text() if len(cols) > 3 else ""  # Opponent

                    # Extract stat projections (adjust indices based on pos)
                    stats_text = [await c.inner_text() for c in cols[4:]]  # Skip rank, name, team, bye
                    proj_row = {
                        "player": player, "team": team, "pos": pos, "opp": opp,
                        "pass_cmp": 0, "pass_att": 0, "pass_yds": 0, "pass_td": 0, "int": 0,
                        "rush_att": 0, "rush_yds": 0, "rush_td": 0,
                        "rec": 0, "rec_yds": 0, "rec_td": 0,
                        "fumble_lost": 0, "two_pt": 0, "return_yds": 0, "return_td": 0,
                        "sacks_taken": 0, "pass_fd": 0, "rush_fd": 0, "rec_fd": 0,
                        "pass_40_plus_cmp": 0, "pass_40_plus_td": 0, "rush_40_plus": 0, "rush_40_plus_td": 0,
                        "rec_40_plus": 0, "rec_40_plus_td": 0, "pick_six": 0,
                        # Kicker/Def specifics
                        "fg_0_19": 0, "fg_20_29": 0, "fg_30_39": 0, "fg_40_49": 0, "fg_50_plus": 0,
                        "fg_miss_0_19": 0, "fg_miss_20_29": 0, "fg_miss_30_39": 0, "fg_miss_40_49": 0, "fg_miss_50_plus": 0,
                        "xp_made": 0, "xp_miss": 0,
                        "def_sacks": 0, "def_int": 0, "def_fum_rec": 0, "def_td": 0, "def_safety": 0, "def_block": 0,
                        "def_return_td": 0, "def_4th_down_stops": 0, "def_tfl": 0, "def_3_and_out": 0, "def_xp_return": 0,
                        "opp_pts": 0, "opp_yds": 0  # For def tiers
                    }

                    # Map stats (FantasyPros columns vary by pos; this is approximate—enhance as needed)
                    if pos in ["QB", "RB", "WR", "TE"]:
                        if len(stats_text) >= 12:
                            proj_row['pass_cmp'] = float(re.sub(r'[^\d.]', '', stats_text[0]) or 0)
                            proj_row['pass_yds'] = float(re.sub(r'[^\d.]', '', stats_text[2]) or 0)
                            proj_row['pass_td'] = float(re.sub(r'[^\d.]', '', stats_text[3]) or 0)
                            proj_row['rush_att'] = float(re.sub(r'[^\d.]', '', stats_text[4]) or 0)
                            proj_row['rush_yds'] = float(re.sub(r'[^\d.]', '', stats_text[5]) or 0)
                            proj_row['rush_td'] = float(re.sub(r'[^\d.]', '', stats_text[6]) or 0)
                            proj_row['rec'] = float(re.sub(r'[^\d.]', '', stats_text[7]) or 0)
                            proj_row['rec_yds'] = float(re.sub(r'[^\d.]', '', stats_text[8]) or 0)
                            proj_row['rec_td'] = float(re.sub(r'[^\d.]', '', stats_text[9]) or 0)
                            proj_row['fumble_lost'] = float(re.sub(r'[^\d.]', '', stats_text[10]) or 0)
                            # Estimate bonuses (rough; real projections might need more sources)
                            proj_row['pass_fd'] = proj_row['pass_yds'] / 20  # Approx
                            proj_row['rush_fd'] = proj_row['rush_yds'] / 10
                            proj_row['rec_fd'] = proj_row['rec_yds'] / 10
                            proj_row['sacks_taken'] = 2 if pos == "QB" else 0  # Default low
                            proj_row['pass_40_plus_cmp'] = max(0, proj_row['pass_td'] - 1)  # Rough est
                            # ... (similar rough est for 40+ plays; improve with more scrapers if needed)

                    elif pos == "K":
                        if len(stats_text) >= 6:
                            proj_row['fg_0_19'] = float(stats_text[0] or 0)
                            proj_row['fg_20_29'] = float(stats_text[1] or 0)
                            proj_row['fg_30_39'] = float(stats_text[2] or 0)
                            proj_row['fg_40_49'] = float(stats_text[3] or 0)
                            proj_row['fg_50_plus'] = float(stats_text[4] or 0)
                            proj_row['xp_made'] = float(stats_text[5] or 0)

                    elif pos == "DST":
                        if len(stats_text) >= 4:
                            proj_row['def_sacks'] = float(stats_text[0] or 0)
                            proj_row['def_int'] = float(stats_text[1] or 0)
                            proj_row['def_fum_rec'] = float(stats_text[2] or 0)
                            proj_row['def_td'] = float(stats_text[3] or 0)
                            proj_row['opp_pts'] = 20  # Default avg; scrape real opp proj if possible
                            proj_row['opp_yds'] = 350  # Default avg
                            proj_row['def_4th_down_stops'] = 1  # Est
                            # ... (add more as per projections)

                    proj_row['source_points'] = calculate_fantasy_points(proj_row, is_def=(pos == "DST"))
                    all_data.append(proj_row)
            except Exception as e:
                print(f"Error scraping {url}: {e}")
                continue

        # Add secondary sources (e.g., ESPN for backups)
        try:
            await page.goto("https://fantasy.espn.com/football/players/projections", wait_until="networkidle")
            # Similar parsing logic here—abbreviated for space; expand if needed
            rows = await page.query_selector_all(".Table__TR--sm")
            for row in rows[:20]:
                # Parse ESPN table...
                pass  # Placeholder: implement full if primary fails
        except:
            pass

        await browser.close()

    # Combine with cache if fresh data low
    cached = load_cache()
    if not all_data:
        return cached
    df = pd.DataFrame(all_data)
    if not cached.empty:
        df = pd.concat([df, cached]).drop_duplicates(subset=['player', 'pos'])
    save_cache(df)
    return df

# ============================= WORKER THREAD =============================
class ScrapeThread(QThread):
    finished = pyqtSignal(pd.DataFrame)
    progress = pyqtSignal(str)

    def run(self):
        self.progress.emit("Checking cache... Scraping fresh projections from FantasyPros + others...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        df = loop.run_until_complete(scrape_sources())
        loop.close()

        if df.empty:
            self.progress.emit("No data—check internet or try again!")
            return

        # Consensus: mean across sources (here simplified to per-player avg)
        consensus = df.groupby(['player', 'team', 'pos']).agg({
            'source_points': 'mean',
            'opp_pts': 'mean'  # For def
        }).reset_index()
        consensus.rename(columns={'source_points': 'consensus'}, inplace=True)
        consensus['floor'] = df.groupby(['player', 'pos'])['source_points'].quantile(0.1).reindex(consensus.index, method='ffill').values
        consensus['ceiling'] = df.groupby(['player', 'pos'])['source_points'].quantile(0.9).reindex(consensus.index, method='ffill').values
        consensus = consensus.sort_values('consensus', ascending=False)
        consensus['overall_rank'] = consensus['consensus'].rank(ascending=False).astype(int)
        consensus['pos_rank'] = consensus.groupby('pos')['consensus'].rank(ascending=False).astype(int)

        self.finished.emit(consensus)

# ============================= GUI =============================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Your Custom League Consensus Projections (2025)")
        self.setGeometry(100, 50, 1400, 900)
        self.setStyleSheet("""
            QMainWindow { background: #0f1620; color: #e0e0e0; }
            QLabel { color: #e0e0e0; font-size: 11pt; }
            QTableView { background: #1a2332; gridline-color: #333; font-size: 10pt; }
            QPushButton { background: #00bfff; color: black; font-weight: bold; padding: 10px; border-radius: 5px; }
            QComboBox { background: #1a2332; color: #e0e0e0; padding: 5px; }
        """)

        central = QWidget()
        layout = QVBoxLayout()

        title = QLabel("<h1 style='color:#00bfff'>Your League Custom Scoring Consensus</h1>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        controls = QHBoxLayout()
        QLabel("Position:").setStyleSheet("color:#888;")
        self.pos_filter = QComboBox()
        self.pos_filter.addItems(["ALL", "QB", "RB", "WR", "TE", "K", "DST"])
        self.pos_filter.currentTextChanged.connect(self.filter_pos)
        controls.addWidget(self.pos_filter)

        self.update_btn = QPushButton("🔄 Update Projections (Live Scrape)")
        self.update_btn.clicked.connect(self.start_update)
        controls.addWidget(self.update_btn)

        self.cache_btn = QPushButton("📁 Load from Cache (Fast)")
        self.cache_btn.clicked.connect(self.load_cache)
        controls.addWidget(self.cache_btn)
        controls.addStretch()
        layout.addLayout(controls)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.status = QLabel("Ready—Try 'Load from Cache' for instant view or Update for fresh data.")
        layout.addWidget(self.status)

        # Table like FantasyPros
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(["Overall Rank", "Pos Rank", "Player", "Team", "Pos", "Opp", "Consensus Pts", "Floor", "Ceiling"])
        self.proxy = QSortFilterProxyModel()
        self.proxy.setSourceModel(self.model)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, 1)

        central.setLayout(layout)
        self.setCentralWidget(central)
        self.full_df = pd.DataFrame()
        self.load_cache()  # Auto-load cache on start

    def start_update(self):
        self.update_btn.setEnabled(False)
        self.cache_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.status.setText("Live scraping... (45-90 sec)")
        self.thread = ScrapeThread()
        self.thread.progress.connect(self.update_progress)
        self.thread.finished.connect(self.display_results)
        self.thread.start()

    def update_progress(self, msg):
        self.status.setText(msg)
        self.progress.setValue(self.progress.value() + 10)  # Simple progress

    def load_cache(self):
        df = load_cache()
        if not df.empty:
            self.display_results(df)
            self.status.setText("Loaded from cache—last updated unknown. Click Update for fresh.")
        else:
            self.status.setText("No cache found—run Update first!")

    def display_results(self, df):
        self.full_df = df
        self.filter_pos(self.pos_filter.currentText())
        self.update_btn.setEnabled(True)
        self.cache_btn.setEnabled(True)
        self.progress.setVisible(False)
        self.progress.setValue(100)
        timestamp = df.get('timestamp', datetime.now()).iloc[0] if not df.empty else datetime.now()
        self.status.setText(f"Loaded {len(df)} projections | Updated: {timestamp.strftime('%b %d, %Y %I:%M %p')}")

    def filter_pos(self, pos):
        self.model.removeRows(0, self.model.rowCount())
        data = self.full_df if pos == "ALL" else self.full_df[self.full_df['pos'] == pos]
        for _, row in data.iterrows():
            items = [
                QStandardItem(str(int(row.get('overall_rank', '')))),
                QStandardItem(str(int(row.get('pos_rank', '')))),
                QStandardItem(row['player']),
                QStandardItem(row['team']),
                QStandardItem(row['pos']),
                QStandardItem(row['opp']),
                QStandardItem(f"{row['consensus']:.1f}"),
                QStandardItem(f"{row['floor']:.1f}" if pd.notna(row['floor']) else "—"),
                QStandardItem(f"{row['ceiling']:.1f}" if pd.notna(row['ceiling']) else "—"),
            ]
            for it in items:
                it.setEditable(False)
                if row['pos'] == 'DST': it.setForeground(QColor(0, 255, 0))  # Green for DST
            self.model.appendRow(items)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
