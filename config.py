SERVICE_TYPES = {
    "Рихтовка/покраска": {
        "subtypes": ["Кузовна рихтовка", "Повна покраска", "Локальна покраска"],
        "requires_datetime": True,
        "calendar_id": "gdg1234576543@gmail.com",
        "chat_id": "-1002660061190"  # ID групи
    },
    "ГБО": {
        "subtypes": ["Встановлення ГБО", "Обслуговування", "Заміна балона"],
        "requires_datetime": True,
        "calendar_id": "gdg1234576543@gmail.com",
        "chat_id": "-1002765451748"  # ID групи
    },
    "СТО": {
        "subtypes": ["Заміна масла", "Діагностика", "Техобслуговування"],
        "requires_datetime": True,
        "calendar_id": "gdg1234576543@gmail.com",
        "chat_id": "-1002757872602"  # ID групи
    }
}


POPULAR_CARS = {
    "Volkswagen": [
        "Golf", "Polo", "Passat", "Tiguan", "T-Roc", "Touran", "Arteon",
        "ID.3", "ID.4", "Up!", "Taigo", "Sharan", "Jetta", "Caddy",
        "Transporter"
    ],
    "Toyota": [
        "Corolla", "Yaris", "C-HR", "RAV4", "Camry", "Aygo", "Highlander",
        "Land Cruiser", "Hilux", "Avensis", "Verso", "Proace", "Prius", "GR86",
        "Supra"
    ],
    "Peugeot": [
        "208", "308", "2008", "3008", "5008", "508", "107", "207", "Traveller",
        "Rifter", "Expert", "Partner", "Boxer", "Bipper", "4008"
    ],
    "Renault": [
        "Clio", "Captur", "Megane", "Kadjar", "Scenic", "Talisman", "Twingo",
        "ZOE", "Laguna", "Arkana", "Austral", "Koleos", "Espace", "Trafic",
        "Master"
    ],
    "Skoda": [
        "Octavia", "Fabia", "Kamiq", "Karoq", "Kodiaq", "Superb", "Rapid",
        "Scala", "Citigo", "Enyaq", "Yeti", "Roomster", "Felicia", "Forman",
        "Favorit"
    ],
    "BMW": [
        "1 Series", "2 Series", "3 Series", "4 Series", "5 Series", "6 Series",
        "7 Series", "8 Series", "X1", "X2", "X3", "X4", "X5", "X6", "i3"
    ],
    "Mercedes": [
        "A-Class", "B-Class", "C-Class", "E-Class", "S-Class", "GLA", "GLB",
        "GLC", "GLE", "GLS", "CLA", "CLS", "EQC", "EQB", "Sprinter"
    ],
    "Audi": [
        "A1", "A3", "A4", "A5", "A6", "A7", "A8", "Q2", "Q3", "Q5", "Q7", "Q8",
        "TT", "e-tron", "RS6"
    ],
    "Ford": [
        "Fiesta", "Focus", "Puma", "Kuga", "Mondeo", "Galaxy", "S-MAX",
        "EcoSport", "Tourneo", "Transit", "Ranger", "Ka+", "Explorer", "Edge",
        "C-Max"
    ],
    "Fiat": [
        "500", "Panda", "Tipo", "500X", "500L", "Doblo", "Punto", "Bravo",
        "Fiorino", "Qubo", "Linea", "Croma", "Idea", "Multipla", "Freemont"
    ],
    "Kia": [
        "Ceed", "Sportage", "Rio", "Picanto", "Stonic", "Niro", "Sorento",
        "Optima", "Carens", "XCeed", "EV6", "Soul", "Cerato", "Seltos",
        "Mohave"
    ],
    "Hyundai": [
        "i10", "i20", "i30", "Tucson", "Santa Fe", "Kona", "Bayon", "Ioniq 5",
        "Ioniq 6", "Elantra", "Sonata", "Accent", "Terracan", "Matrix", "Atos"
    ],
    "Seat": [
        "Ibiza", "Leon", "Arona", "Ateca", "Tarraco", "Toledo", "Altea",
        "Cordoba", "Alhambra", "Mii", "Exeo", "Marbella", "Fura", "Inca",
        "Malaga"
    ],
    "Opel": [
        "Corsa", "Astra", "Mokka", "Grandland", "Crossland", "Insignia",
        "Zafira", "Meriva", "Combo", "Vivaro", "Adam", "Ampera", "Tigra",
        "Vectra", "Omega"
    ],
    "Dacia": [
        "Sandero", "Logan", "Duster", "Spring", "Jogger", "Dokker", "Lodgy",
        "1300", "1304", "1310", "Nova", "Solenza", "Pick-Up", "SuperNova",
        "Manifesto"
    ],
    "Chevrolet": [
        "Aveo", "Cruze", "Cobalt", "Captiva", "Orlando", "Malibu",
        "Camaro", "Tahoe", "Blazer", "Equinox", "Suburban"
    ],
}