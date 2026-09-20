import re
from typing import List

# Base URLs for eprocure CPPP
BASE_URL = "https://eprocure.gov.in"
CPPP_CENTRAL_URL = "https://eprocure.gov.in/cppp/latestactivetendersnew/cpppdata"
CPPP_STATES_URL = "https://eprocure.gov.in/cppp/latestactivetendersnew/mmpdata"
CPPP_GEM_URL = "https://eprocure.gov.in/cppp/latestactivetendersnew/gemdata"
CPPP_GEM_SEARCH_URL = "https://eprocure.gov.in/cppp/gemtender"

SOURCES = {
    "central": {
        "name": "Central Government Tenders",
        "url": CPPP_CENTRAL_URL,
        "type": "category_dropdown",
    },
    "states": {
        "name": "State Government Tenders",
        "url": CPPP_STATES_URL,
        "type": "category_dropdown",
    },
    "gem": {
        "name": "GeM Bids",
        "url": CPPP_GEM_SEARCH_URL,
        "type": "keyword_search",
    },
}

# Regex pattern to automatically identify IT / Tech categories from portal dropdown options
IT_CATEGORY_REGEX = re.compile(
    r"\b(IT|Tech|Technology|Computer|Software|Hardware|Network|Networking|Digitisation|Digitization|Data Processing|Telecom|Telecommunication|OFC)\b",
    re.IGNORECASE
)


def is_it_category(category_name: str) -> bool:
    """Check if a portal product category string is relevant to IT / Tech."""
    return bool(IT_CATEGORY_REGEX.search(category_name))


def filter_it_categories(category_list: List[str]) -> List[str]:
    """Filter a list of category option names, keeping only IT / Tech related ones."""
    return [c for c in category_list if is_it_category(c)]


# Standard IT product categories found in CPPP s_prod_type dropdown
IT_PRODUCT_CATEGORIES = [
    "Info. Tech. Services",
    "Information Technology (IT)",
    "Information Technology/Telecom",
    "IT Services",
    "IT - All",
    "IT",
    "Computer Software/Web Site",
    "Computer Hardware",
    "Computer Data Processing",
    "Network /Communication Equipments",
    "Scanning, Digitisation Services",
    "OFC Laying Works",
]

# Keywords for searching GeM bids
GEM_IT_KEYWORDS = [
    "Information Technology",
    "IT Services",
    "Computer Software",
    "Computer Hardware",
]

# Standard HTTP headers mimicking desktop browser
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Referer": "https://eprocure.gov.in/cppp/latestactivetendersnew",
}

DEFAULT_TIMEOUT = 25
DEFAULT_DELAY = 1.0
MAX_RETRIES = 4
BACKOFF_FACTOR = 1.5

# IT Taxonomies & Keywords
IT_CATEGORIES = {
    "Software & Applications": [
        "software", "web portal", "website", "web application", "mobile app",
        "android app", "ios app", "erp", "crm", "sap erp", "sap software",
        "sap implementation", "database", "dbms", "sql", "frontend", "backend",
        "api ", "microservice", "ai/ml", "artificial intelligence",
        "machine learning", "deep learning", "llm", "chatbot",
        "business intelligence", "bi tool", "billing system",
        "workflow system", "content management system", "cms software",
        "cms portal", "lms", "gis mapping", "gis software", "gis survey",
        "e-office", "eoffice", "software development", "software maintenance",
        "custom software", "mobile application", "portal development",
        "software license"
    ],
    "Cloud & Data Center": [
        "cloud", "datacenter", "data center", "aws", "azure", "meghraj",
        "server hosting", "virtualization", "vmware", "hyper-v",
        "cloud storage", "disaster recovery", "dr site", "co-location",
        "colocation", "kubernetes", "docker", "devops",
        "infrastructure as a service", "platform as a service",
        "software as a service", "cloud services", "cloud solution"
    ],
    "Networking & Cybersecurity": [
        "networking", "lan ", "wan ", "sd-wan", "network switch", "router",
        "firewall", "utm ", "siem", "soc ", "antivirus", "cyber security",
        "cybersecurity", "penetration testing", "vapt", "vulnerability assessment",
        "ids/ips", "ssl certificate", "vpn", "optical fiber", "ofc cable",
        "ofc laying", "leased line", "internet bandwidth", "wi-fi", "wifi",
        "structured cabling", "network rack", "network security"
    ],
    "Hardware & Computing": [
        "computer", "computers", "desktop", "desktops", "desktop computer",
        "computer system", "computer hardware", "pc", "pcs", "laptop",
        "laptops", "notebook computer", "workstation", "workstations",
        "server", "servers", "rack server", "blade server", "storage server",
        "san storage", "nas storage", "interactive display",
        "interactive flat panel", "ifpd", "smart classroom", "smart board",
        "ups", "line interactive ups", "online ups", "thin client",
        "all in one pc", "aio pc", "printer", "printers", "multifunction printer",
        "scanner", "scanners", "biometric device", "biometric attendance",
        "cctv", "ip camera", "surveillance system", "nvr", "dvr"
    ],
    "IT Services & Consulting": [
        "it amc", "it facility management", "fms", "system integrator",
        "system integration", "it technical support", "it helpdesk",
        "it consulting", "it manpower", "it engineer", "it technician",
        "annual maintenance contract for computer", "annual maintenance contract for computers",
        "amc of computer", "amc of computers", "amc for computer", "amc for computers",
        "amc for it", "it asset management", "it support services",
        "annual maintenance contract", "maintenance contract", "amc"
    ],
    "Digitization & Data Processing": [
        "digitization", "digitisation", "document scanning", "scanning and indexing",
        "data entry", "ocr", "record management system", "data processing",
        "document management system", "dms software", "smart card", "rfid"
    ]
}

# Recognized Premier IT Government Bodies / PSUs
IT_ORGANISATIONS = [
    "national informatics centre",
    "nicsi",
    "centre for development of advanced computing",
    "c-dac",
    "cdac",
    "software technology parks of india",
    "stpi",
    "ministry of electronics and information technology",
    "meity",
    "department of electronics and information technology",
    "iti limited",
    "telecommunications consultants india limited",
    "tcil",
    "railtel",
    "centre for development of telematics",
    "c-dot",
    "cdot",
    "digital india corporation",
    "national e-governance division",
    "negd",
    "indian computer emergency response team",
    "cert-in",
    "national internet exchange of india",
    "nixi",
    "ernet india",
    "semi-conductor laboratory",
    "reservebank information technology"
]

# Negative exclusion patterns to avoid false positives (e.g., civil works with "computer" room)
EXCLUSION_KEYWORDS = [
    "civil works", "construction of", "renovation of building",
    "renovation of", "remodeling", "up gradation for working space",
    "interior work", "furniture", "fencing", "civil engineering",
    "repair of road", "road work", "bitumen", "concrete road",
    "drainage", "sewerage", "pipeline laying", "plumbing work",
    "painting work", "masonry", "sand blasting", "earth work",
    "excavation work", "catering service", "housekeeping cleaning",
    "sweeping", "horticulture", "garden maintenance", "security guards",
    "vehicle hiring", "hiring of vehicle", "diesel supply", "petrol supply",
    "medical waste", "surgical items", "pathology reagents",
    "supply of bricks", "supply of sand", "cement supply",
    "cc road", "naali nirman", "sadak nirman", "nirman karya",
    "marammat karya", "interlocking", "kharanja"
]
