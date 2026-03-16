import requests
from bs4 import BeautifulSoup
import datetime
from engagement_course.config import FFC_CALENDAR_URLS, DATE_FORMAT
from engagement_course.models import RaceEvent, Category

FRENCH_MONTHS = {
    "janvier": "01", "février": "02", "mars": "03", "avril": "04",
    "mai": "05", "juin": "06", "juillet": "07", "aout": "08",
    "septembre": "09", "octobre": "10", "novembre": "11", "décembre": "12"
}

class FFCParser:
    def __init__(self, department: int=35):
        self.department = department
        self.url = FFC_CALENDAR_URLS.get(department)
        if self.url is None:
            raise ValueError(f"No calendar URL configured for department {department}. Please check FFC_CALENDAR_URLS in config.py.")

    def fetch_calendar(self) -> str:
        """
        Fetches the HTML content of the FFC calendar page.

        Returns:
            The raw HTML content as a string.
        """
        response = requests.get(self.url, timeout=15)
        if response.status_code == 200:
            return response.text
        else:
            raise Exception(f"Failed to fetch calendar: {response.status_code}")

    def parse_calendar(self, html: str) -> list[RaceEvent]:
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
                        date=datetime.datetime.strptime(day.split()[1]+"/"+month_num+"/"+year, "%d/%m/%Y").date(),
                        location=cells[1-index_offset].text.strip().replace(" .", ""),
                        department=self.department,
                        federation=cells[2-index_offset].text.strip(),
                        type=cells[3-index_offset].text.strip(),
                        categories=Category.from_string(cells[4-index_offset].text.strip())
                    )
                races.append(race)
        return races
