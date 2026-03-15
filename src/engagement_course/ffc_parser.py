import requests
from bs4 import BeautifulSoup
import datetime
from .config import FFC_CALENDAR_URL
from .models import RaceEvent, Category

FRENCH_MONTHS = {
    "janvier": "01", "février": "02", "mars": "03", "avril": "04",
    "mai": "05", "juin": "06", "juillet": "07", "aout": "08",
    "septembre": "09", "octobre": "10", "novembre": "11", "décembre": "12"
}

class FFCParser:
    def __init__(self, url=FFC_CALENDAR_URL):
        self.url = url

    def fetch_calendar(self) -> str:
        """
        Fetches the HTML content of the FFC calendar page.

        Returns:
            The raw HTML content as a string.
        """
        response = requests.get(self.url)
        if response.status_code == 200:
            return response.text
        else:
            raise Exception(f"Failed to fetch calendar: {response.status_code}")

    def parse_calendar(self, html: str) -> list:
        """
        Parses the HTML content to extract event details.

        Args:
            html: The raw HTML content of the calendar page.
        Returns:
            A list of RaceEvent objects.
        """
        soup = BeautifulSoup(html, 'html.parser')
        races = []
        for table in soup.find_all('table', class_='avec-contour'):
            b = table.find('b').text.strip()
            month_name = b.split()[0].lower()
            year = b.split()[1]
            month_num = FRENCH_MONTHS.get(month_name, "01")
            rows = table.find_all('tr', class_="ligne_de_course")
            for row in rows:
                cells = row.find_all('td')
                if len(cells) == 5:
                    day = cells[0].text.strip()
                    curr_day = day
                    index_offset = 0
                elif len(cells) == 4:
                    day = curr_day
                    index_offset = 1
                else:
                    raise Exception(f"Unexpected number of cells: {len(cells)}.\nRow content: {row}")
                race = RaceEvent(
                        race_day = day.split()[0],
                        date=datetime.datetime.strptime(day.split()[1]+"/"+month_num+"/"+year, "%d/%m/%Y").date().strftime('%d-%m-%Y'),
                        location=cells[1-index_offset].text.strip().replace(" .", ""),
                        federation=cells[2-index_offset].text.strip(),
                        type=cells[3-index_offset].text.strip(),
                        categories=self.parse_categories(cells[4-index_offset].text.strip())
                    )
                races.append(race)
        return races

    def parse_categories(self, raw_category: str) -> list[Category]:
        """
        Parses a raw category string into a list of Category objects.

        Args:
            raw_category: The raw category string (e.g., "OPEN 1,2,3 + ACCESS 1 ET 2").
        Returns:
            A list of Category objects.
        """
        category_labels = ["OPEN", "ACCESS"]
        categories = []
        for part in raw_category.split('+'):
            level = next((label for label in category_labels if label in part), None)
            if level is None:
                continue  # Skip unsupported categories
            for c in part:
                if c.isdigit():
                    categories.append(Category(level=level, number=int(c)))
        return categories