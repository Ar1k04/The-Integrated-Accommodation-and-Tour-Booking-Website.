"""IATA airport master list for autocomplete.

Curated list of ~280 airports — all Vietnamese airports, all major SE Asia hubs,
and the busiest hubs globally. Source-of-truth for the /flights/airports
endpoint. Format: {iata, name, city, country}.
"""

AIRPORTS: list[dict[str, str]] = [
    # Vietnam
    {"iata": "HAN", "name": "Noi Bai International", "city": "Hanoi", "country": "Vietnam"},
    {"iata": "SGN", "name": "Tan Son Nhat International", "city": "Ho Chi Minh City", "country": "Vietnam"},
    {"iata": "DAD", "name": "Da Nang International", "city": "Da Nang", "country": "Vietnam"},
    {"iata": "CXR", "name": "Cam Ranh International", "city": "Nha Trang", "country": "Vietnam"},
    {"iata": "PQC", "name": "Phu Quoc International", "city": "Phu Quoc", "country": "Vietnam"},
    {"iata": "HPH", "name": "Cat Bi International", "city": "Hai Phong", "country": "Vietnam"},
    {"iata": "HUI", "name": "Phu Bai International", "city": "Hue", "country": "Vietnam"},
    {"iata": "VCA", "name": "Can Tho International", "city": "Can Tho", "country": "Vietnam"},
    {"iata": "VCS", "name": "Con Dao", "city": "Con Dao", "country": "Vietnam"},
    {"iata": "DLI", "name": "Lien Khuong", "city": "Da Lat", "country": "Vietnam"},
    {"iata": "VDH", "name": "Dong Hoi", "city": "Dong Hoi", "country": "Vietnam"},
    {"iata": "UIH", "name": "Phu Cat", "city": "Quy Nhon", "country": "Vietnam"},
    {"iata": "TBB", "name": "Tuy Hoa", "city": "Tuy Hoa", "country": "Vietnam"},
    {"iata": "VKG", "name": "Rach Gia", "city": "Rach Gia", "country": "Vietnam"},
    {"iata": "BMV", "name": "Buon Ma Thuot", "city": "Buon Ma Thuot", "country": "Vietnam"},
    {"iata": "VII", "name": "Vinh International", "city": "Vinh", "country": "Vietnam"},
    {"iata": "THD", "name": "Tho Xuan", "city": "Thanh Hoa", "country": "Vietnam"},
    {"iata": "CAH", "name": "Ca Mau", "city": "Ca Mau", "country": "Vietnam"},
    {"iata": "VDO", "name": "Van Don International", "city": "Quang Ninh", "country": "Vietnam"},

    # Southeast Asia
    {"iata": "BKK", "name": "Suvarnabhumi", "city": "Bangkok", "country": "Thailand"},
    {"iata": "DMK", "name": "Don Mueang International", "city": "Bangkok", "country": "Thailand"},
    {"iata": "HKT", "name": "Phuket International", "city": "Phuket", "country": "Thailand"},
    {"iata": "CNX", "name": "Chiang Mai International", "city": "Chiang Mai", "country": "Thailand"},
    {"iata": "USM", "name": "Samui", "city": "Koh Samui", "country": "Thailand"},
    {"iata": "KBV", "name": "Krabi", "city": "Krabi", "country": "Thailand"},
    {"iata": "SIN", "name": "Changi", "city": "Singapore", "country": "Singapore"},
    {"iata": "KUL", "name": "Kuala Lumpur International", "city": "Kuala Lumpur", "country": "Malaysia"},
    {"iata": "PEN", "name": "Penang International", "city": "Penang", "country": "Malaysia"},
    {"iata": "BKI", "name": "Kota Kinabalu International", "city": "Kota Kinabalu", "country": "Malaysia"},
    {"iata": "LGK", "name": "Langkawi International", "city": "Langkawi", "country": "Malaysia"},
    {"iata": "CGK", "name": "Soekarno–Hatta International", "city": "Jakarta", "country": "Indonesia"},
    {"iata": "DPS", "name": "Ngurah Rai International", "city": "Denpasar", "country": "Indonesia"},
    {"iata": "SUB", "name": "Juanda International", "city": "Surabaya", "country": "Indonesia"},
    {"iata": "MNL", "name": "Ninoy Aquino International", "city": "Manila", "country": "Philippines"},
    {"iata": "CEB", "name": "Mactan–Cebu International", "city": "Cebu", "country": "Philippines"},
    {"iata": "DVO", "name": "Francisco Bangoy International", "city": "Davao", "country": "Philippines"},
    {"iata": "PNH", "name": "Phnom Penh International", "city": "Phnom Penh", "country": "Cambodia"},
    {"iata": "REP", "name": "Siem Reap International", "city": "Siem Reap", "country": "Cambodia"},
    {"iata": "VTE", "name": "Wattay International", "city": "Vientiane", "country": "Laos"},
    {"iata": "LPQ", "name": "Luang Prabang International", "city": "Luang Prabang", "country": "Laos"},
    {"iata": "RGN", "name": "Yangon International", "city": "Yangon", "country": "Myanmar"},
    {"iata": "MDL", "name": "Mandalay International", "city": "Mandalay", "country": "Myanmar"},
    {"iata": "BWN", "name": "Brunei International", "city": "Bandar Seri Begawan", "country": "Brunei"},

    # East Asia
    {"iata": "PEK", "name": "Beijing Capital International", "city": "Beijing", "country": "China"},
    {"iata": "PKX", "name": "Beijing Daxing International", "city": "Beijing", "country": "China"},
    {"iata": "PVG", "name": "Shanghai Pudong International", "city": "Shanghai", "country": "China"},
    {"iata": "SHA", "name": "Shanghai Hongqiao International", "city": "Shanghai", "country": "China"},
    {"iata": "CAN", "name": "Guangzhou Baiyun International", "city": "Guangzhou", "country": "China"},
    {"iata": "SZX", "name": "Shenzhen Bao'an International", "city": "Shenzhen", "country": "China"},
    {"iata": "CTU", "name": "Chengdu Shuangliu International", "city": "Chengdu", "country": "China"},
    {"iata": "CKG", "name": "Chongqing Jiangbei International", "city": "Chongqing", "country": "China"},
    {"iata": "XIY", "name": "Xi'an Xianyang International", "city": "Xi'an", "country": "China"},
    {"iata": "KMG", "name": "Kunming Changshui International", "city": "Kunming", "country": "China"},
    {"iata": "HGH", "name": "Hangzhou Xiaoshan International", "city": "Hangzhou", "country": "China"},
    {"iata": "NKG", "name": "Nanjing Lukou International", "city": "Nanjing", "country": "China"},
    {"iata": "WUH", "name": "Wuhan Tianhe International", "city": "Wuhan", "country": "China"},
    {"iata": "XMN", "name": "Xiamen Gaoqi International", "city": "Xiamen", "country": "China"},
    {"iata": "HKG", "name": "Hong Kong International", "city": "Hong Kong", "country": "Hong Kong"},
    {"iata": "MFM", "name": "Macau International", "city": "Macau", "country": "Macau"},
    {"iata": "TPE", "name": "Taoyuan International", "city": "Taipei", "country": "Taiwan"},
    {"iata": "TSA", "name": "Taipei Songshan", "city": "Taipei", "country": "Taiwan"},
    {"iata": "KHH", "name": "Kaohsiung International", "city": "Kaohsiung", "country": "Taiwan"},
    {"iata": "ICN", "name": "Incheon International", "city": "Seoul", "country": "South Korea"},
    {"iata": "GMP", "name": "Gimpo International", "city": "Seoul", "country": "South Korea"},
    {"iata": "PUS", "name": "Gimhae International", "city": "Busan", "country": "South Korea"},
    {"iata": "CJU", "name": "Jeju International", "city": "Jeju", "country": "South Korea"},
    {"iata": "NRT", "name": "Narita International", "city": "Tokyo", "country": "Japan"},
    {"iata": "HND", "name": "Haneda", "city": "Tokyo", "country": "Japan"},
    {"iata": "KIX", "name": "Kansai International", "city": "Osaka", "country": "Japan"},
    {"iata": "ITM", "name": "Itami", "city": "Osaka", "country": "Japan"},
    {"iata": "NGO", "name": "Chubu Centrair International", "city": "Nagoya", "country": "Japan"},
    {"iata": "FUK", "name": "Fukuoka", "city": "Fukuoka", "country": "Japan"},
    {"iata": "CTS", "name": "New Chitose", "city": "Sapporo", "country": "Japan"},
    {"iata": "OKA", "name": "Naha", "city": "Okinawa", "country": "Japan"},
    {"iata": "ULN", "name": "Chinggis Khaan International", "city": "Ulaanbaatar", "country": "Mongolia"},

    # South Asia
    {"iata": "DEL", "name": "Indira Gandhi International", "city": "Delhi", "country": "India"},
    {"iata": "BOM", "name": "Chhatrapati Shivaji Maharaj International", "city": "Mumbai", "country": "India"},
    {"iata": "BLR", "name": "Kempegowda International", "city": "Bangalore", "country": "India"},
    {"iata": "MAA", "name": "Chennai International", "city": "Chennai", "country": "India"},
    {"iata": "HYD", "name": "Rajiv Gandhi International", "city": "Hyderabad", "country": "India"},
    {"iata": "CCU", "name": "Netaji Subhas Chandra Bose International", "city": "Kolkata", "country": "India"},
    {"iata": "GOI", "name": "Goa International", "city": "Goa", "country": "India"},
    {"iata": "COK", "name": "Cochin International", "city": "Kochi", "country": "India"},
    {"iata": "DAC", "name": "Hazrat Shahjalal International", "city": "Dhaka", "country": "Bangladesh"},
    {"iata": "KTM", "name": "Tribhuvan International", "city": "Kathmandu", "country": "Nepal"},
    {"iata": "CMB", "name": "Bandaranaike International", "city": "Colombo", "country": "Sri Lanka"},
    {"iata": "MLE", "name": "Velana International", "city": "Malé", "country": "Maldives"},
    {"iata": "ISB", "name": "Islamabad International", "city": "Islamabad", "country": "Pakistan"},
    {"iata": "KHI", "name": "Jinnah International", "city": "Karachi", "country": "Pakistan"},
    {"iata": "LHE", "name": "Allama Iqbal International", "city": "Lahore", "country": "Pakistan"},

    # Middle East
    {"iata": "DXB", "name": "Dubai International", "city": "Dubai", "country": "United Arab Emirates"},
    {"iata": "AUH", "name": "Abu Dhabi International", "city": "Abu Dhabi", "country": "United Arab Emirates"},
    {"iata": "DWC", "name": "Al Maktoum International", "city": "Dubai", "country": "United Arab Emirates"},
    {"iata": "SHJ", "name": "Sharjah International", "city": "Sharjah", "country": "United Arab Emirates"},
    {"iata": "DOH", "name": "Hamad International", "city": "Doha", "country": "Qatar"},
    {"iata": "BAH", "name": "Bahrain International", "city": "Manama", "country": "Bahrain"},
    {"iata": "KWI", "name": "Kuwait International", "city": "Kuwait City", "country": "Kuwait"},
    {"iata": "RUH", "name": "King Khalid International", "city": "Riyadh", "country": "Saudi Arabia"},
    {"iata": "JED", "name": "King Abdulaziz International", "city": "Jeddah", "country": "Saudi Arabia"},
    {"iata": "MCT", "name": "Muscat International", "city": "Muscat", "country": "Oman"},
    {"iata": "AMM", "name": "Queen Alia International", "city": "Amman", "country": "Jordan"},
    {"iata": "BEY", "name": "Beirut–Rafic Hariri International", "city": "Beirut", "country": "Lebanon"},
    {"iata": "TLV", "name": "Ben Gurion", "city": "Tel Aviv", "country": "Israel"},
    {"iata": "IST", "name": "Istanbul", "city": "Istanbul", "country": "Turkey"},
    {"iata": "SAW", "name": "Sabiha Gokcen International", "city": "Istanbul", "country": "Turkey"},
    {"iata": "AYT", "name": "Antalya", "city": "Antalya", "country": "Turkey"},
    {"iata": "IKA", "name": "Imam Khomeini International", "city": "Tehran", "country": "Iran"},

    # Europe
    {"iata": "LHR", "name": "Heathrow", "city": "London", "country": "United Kingdom"},
    {"iata": "LGW", "name": "Gatwick", "city": "London", "country": "United Kingdom"},
    {"iata": "STN", "name": "Stansted", "city": "London", "country": "United Kingdom"},
    {"iata": "LTN", "name": "Luton", "city": "London", "country": "United Kingdom"},
    {"iata": "LCY", "name": "London City", "city": "London", "country": "United Kingdom"},
    {"iata": "MAN", "name": "Manchester", "city": "Manchester", "country": "United Kingdom"},
    {"iata": "EDI", "name": "Edinburgh", "city": "Edinburgh", "country": "United Kingdom"},
    {"iata": "DUB", "name": "Dublin", "city": "Dublin", "country": "Ireland"},
    {"iata": "CDG", "name": "Charles de Gaulle", "city": "Paris", "country": "France"},
    {"iata": "ORY", "name": "Orly", "city": "Paris", "country": "France"},
    {"iata": "NCE", "name": "Nice Côte d'Azur", "city": "Nice", "country": "France"},
    {"iata": "MRS", "name": "Marseille Provence", "city": "Marseille", "country": "France"},
    {"iata": "LYS", "name": "Lyon–Saint-Exupéry", "city": "Lyon", "country": "France"},
    {"iata": "AMS", "name": "Schiphol", "city": "Amsterdam", "country": "Netherlands"},
    {"iata": "FRA", "name": "Frankfurt", "city": "Frankfurt", "country": "Germany"},
    {"iata": "MUC", "name": "Munich", "city": "Munich", "country": "Germany"},
    {"iata": "BER", "name": "Berlin Brandenburg", "city": "Berlin", "country": "Germany"},
    {"iata": "DUS", "name": "Düsseldorf", "city": "Düsseldorf", "country": "Germany"},
    {"iata": "HAM", "name": "Hamburg", "city": "Hamburg", "country": "Germany"},
    {"iata": "CGN", "name": "Cologne Bonn", "city": "Cologne", "country": "Germany"},
    {"iata": "STR", "name": "Stuttgart", "city": "Stuttgart", "country": "Germany"},
    {"iata": "MAD", "name": "Adolfo Suárez Madrid–Barajas", "city": "Madrid", "country": "Spain"},
    {"iata": "BCN", "name": "Barcelona–El Prat", "city": "Barcelona", "country": "Spain"},
    {"iata": "AGP", "name": "Málaga", "city": "Málaga", "country": "Spain"},
    {"iata": "PMI", "name": "Palma de Mallorca", "city": "Palma", "country": "Spain"},
    {"iata": "FCO", "name": "Leonardo da Vinci–Fiumicino", "city": "Rome", "country": "Italy"},
    {"iata": "CIA", "name": "Ciampino", "city": "Rome", "country": "Italy"},
    {"iata": "MXP", "name": "Milan Malpensa", "city": "Milan", "country": "Italy"},
    {"iata": "LIN", "name": "Milan Linate", "city": "Milan", "country": "Italy"},
    {"iata": "VCE", "name": "Venice Marco Polo", "city": "Venice", "country": "Italy"},
    {"iata": "NAP", "name": "Naples", "city": "Naples", "country": "Italy"},
    {"iata": "BRU", "name": "Brussels", "city": "Brussels", "country": "Belgium"},
    {"iata": "ZRH", "name": "Zürich", "city": "Zurich", "country": "Switzerland"},
    {"iata": "GVA", "name": "Geneva", "city": "Geneva", "country": "Switzerland"},
    {"iata": "VIE", "name": "Vienna International", "city": "Vienna", "country": "Austria"},
    {"iata": "CPH", "name": "Copenhagen", "city": "Copenhagen", "country": "Denmark"},
    {"iata": "ARN", "name": "Stockholm Arlanda", "city": "Stockholm", "country": "Sweden"},
    {"iata": "OSL", "name": "Oslo Gardermoen", "city": "Oslo", "country": "Norway"},
    {"iata": "HEL", "name": "Helsinki-Vantaa", "city": "Helsinki", "country": "Finland"},
    {"iata": "KEF", "name": "Keflavik International", "city": "Reykjavik", "country": "Iceland"},
    {"iata": "LIS", "name": "Lisbon", "city": "Lisbon", "country": "Portugal"},
    {"iata": "OPO", "name": "Porto", "city": "Porto", "country": "Portugal"},
    {"iata": "ATH", "name": "Athens International", "city": "Athens", "country": "Greece"},
    {"iata": "PRG", "name": "Václav Havel Prague", "city": "Prague", "country": "Czech Republic"},
    {"iata": "WAW", "name": "Warsaw Chopin", "city": "Warsaw", "country": "Poland"},
    {"iata": "BUD", "name": "Budapest Ferenc Liszt International", "city": "Budapest", "country": "Hungary"},
    {"iata": "OTP", "name": "Henri Coandă International", "city": "Bucharest", "country": "Romania"},
    {"iata": "SOF", "name": "Sofia", "city": "Sofia", "country": "Bulgaria"},
    {"iata": "SVO", "name": "Sheremetyevo International", "city": "Moscow", "country": "Russia"},
    {"iata": "DME", "name": "Domodedovo International", "city": "Moscow", "country": "Russia"},
    {"iata": "LED", "name": "Pulkovo", "city": "Saint Petersburg", "country": "Russia"},

    # North America - USA
    {"iata": "JFK", "name": "John F. Kennedy International", "city": "New York", "country": "United States"},
    {"iata": "LGA", "name": "LaGuardia", "city": "New York", "country": "United States"},
    {"iata": "EWR", "name": "Newark Liberty International", "city": "Newark", "country": "United States"},
    {"iata": "LAX", "name": "Los Angeles International", "city": "Los Angeles", "country": "United States"},
    {"iata": "SFO", "name": "San Francisco International", "city": "San Francisco", "country": "United States"},
    {"iata": "SJC", "name": "Norman Y. Mineta San José International", "city": "San Jose", "country": "United States"},
    {"iata": "OAK", "name": "Oakland International", "city": "Oakland", "country": "United States"},
    {"iata": "SAN", "name": "San Diego International", "city": "San Diego", "country": "United States"},
    {"iata": "SEA", "name": "Seattle–Tacoma International", "city": "Seattle", "country": "United States"},
    {"iata": "PDX", "name": "Portland International", "city": "Portland", "country": "United States"},
    {"iata": "LAS", "name": "Harry Reid International", "city": "Las Vegas", "country": "United States"},
    {"iata": "PHX", "name": "Phoenix Sky Harbor International", "city": "Phoenix", "country": "United States"},
    {"iata": "DEN", "name": "Denver International", "city": "Denver", "country": "United States"},
    {"iata": "SLC", "name": "Salt Lake City International", "city": "Salt Lake City", "country": "United States"},
    {"iata": "DFW", "name": "Dallas/Fort Worth International", "city": "Dallas", "country": "United States"},
    {"iata": "IAH", "name": "George Bush Intercontinental", "city": "Houston", "country": "United States"},
    {"iata": "HOU", "name": "William P. Hobby", "city": "Houston", "country": "United States"},
    {"iata": "AUS", "name": "Austin–Bergstrom International", "city": "Austin", "country": "United States"},
    {"iata": "MSP", "name": "Minneapolis–Saint Paul International", "city": "Minneapolis", "country": "United States"},
    {"iata": "ORD", "name": "O'Hare International", "city": "Chicago", "country": "United States"},
    {"iata": "MDW", "name": "Midway International", "city": "Chicago", "country": "United States"},
    {"iata": "DTW", "name": "Detroit Metropolitan", "city": "Detroit", "country": "United States"},
    {"iata": "ATL", "name": "Hartsfield–Jackson Atlanta International", "city": "Atlanta", "country": "United States"},
    {"iata": "MIA", "name": "Miami International", "city": "Miami", "country": "United States"},
    {"iata": "FLL", "name": "Fort Lauderdale–Hollywood International", "city": "Fort Lauderdale", "country": "United States"},
    {"iata": "MCO", "name": "Orlando International", "city": "Orlando", "country": "United States"},
    {"iata": "TPA", "name": "Tampa International", "city": "Tampa", "country": "United States"},
    {"iata": "CLT", "name": "Charlotte Douglas International", "city": "Charlotte", "country": "United States"},
    {"iata": "BNA", "name": "Nashville International", "city": "Nashville", "country": "United States"},
    {"iata": "BOS", "name": "Logan International", "city": "Boston", "country": "United States"},
    {"iata": "PHL", "name": "Philadelphia International", "city": "Philadelphia", "country": "United States"},
    {"iata": "BWI", "name": "Baltimore/Washington International", "city": "Baltimore", "country": "United States"},
    {"iata": "DCA", "name": "Ronald Reagan Washington National", "city": "Washington", "country": "United States"},
    {"iata": "IAD", "name": "Washington Dulles International", "city": "Washington", "country": "United States"},
    {"iata": "HNL", "name": "Daniel K. Inouye International", "city": "Honolulu", "country": "United States"},
    {"iata": "ANC", "name": "Ted Stevens Anchorage International", "city": "Anchorage", "country": "United States"},

    # North America - Canada
    {"iata": "YYZ", "name": "Toronto Pearson International", "city": "Toronto", "country": "Canada"},
    {"iata": "YUL", "name": "Montréal–Trudeau International", "city": "Montreal", "country": "Canada"},
    {"iata": "YVR", "name": "Vancouver International", "city": "Vancouver", "country": "Canada"},
    {"iata": "YYC", "name": "Calgary International", "city": "Calgary", "country": "Canada"},
    {"iata": "YEG", "name": "Edmonton International", "city": "Edmonton", "country": "Canada"},
    {"iata": "YOW", "name": "Ottawa Macdonald–Cartier International", "city": "Ottawa", "country": "Canada"},
    {"iata": "YHZ", "name": "Halifax Stanfield International", "city": "Halifax", "country": "Canada"},
    {"iata": "YWG", "name": "Winnipeg James Armstrong Richardson International", "city": "Winnipeg", "country": "Canada"},

    # Mexico & Central America
    {"iata": "MEX", "name": "Mexico City International", "city": "Mexico City", "country": "Mexico"},
    {"iata": "CUN", "name": "Cancún International", "city": "Cancún", "country": "Mexico"},
    {"iata": "GDL", "name": "Guadalajara International", "city": "Guadalajara", "country": "Mexico"},
    {"iata": "MTY", "name": "Monterrey International", "city": "Monterrey", "country": "Mexico"},
    {"iata": "SJD", "name": "Los Cabos International", "city": "Los Cabos", "country": "Mexico"},
    {"iata": "PVR", "name": "Puerto Vallarta International", "city": "Puerto Vallarta", "country": "Mexico"},
    {"iata": "PTY", "name": "Tocumen International", "city": "Panama City", "country": "Panama"},
    {"iata": "SJO", "name": "Juan Santamaría International", "city": "San José", "country": "Costa Rica"},
    {"iata": "GUA", "name": "La Aurora International", "city": "Guatemala City", "country": "Guatemala"},

    # South America
    {"iata": "GRU", "name": "São Paulo–Guarulhos International", "city": "São Paulo", "country": "Brazil"},
    {"iata": "CGH", "name": "Congonhas", "city": "São Paulo", "country": "Brazil"},
    {"iata": "GIG", "name": "Rio de Janeiro–Galeão International", "city": "Rio de Janeiro", "country": "Brazil"},
    {"iata": "BSB", "name": "Brasília International", "city": "Brasília", "country": "Brazil"},
    {"iata": "EZE", "name": "Ministro Pistarini International", "city": "Buenos Aires", "country": "Argentina"},
    {"iata": "SCL", "name": "Arturo Merino Benítez International", "city": "Santiago", "country": "Chile"},
    {"iata": "LIM", "name": "Jorge Chávez International", "city": "Lima", "country": "Peru"},
    {"iata": "BOG", "name": "El Dorado International", "city": "Bogotá", "country": "Colombia"},
    {"iata": "UIO", "name": "Mariscal Sucre International", "city": "Quito", "country": "Ecuador"},
    {"iata": "CCS", "name": "Simón Bolívar International", "city": "Caracas", "country": "Venezuela"},
    {"iata": "MVD", "name": "Carrasco International", "city": "Montevideo", "country": "Uruguay"},

    # Oceania
    {"iata": "SYD", "name": "Kingsford Smith", "city": "Sydney", "country": "Australia"},
    {"iata": "MEL", "name": "Tullamarine", "city": "Melbourne", "country": "Australia"},
    {"iata": "BNE", "name": "Brisbane", "city": "Brisbane", "country": "Australia"},
    {"iata": "PER", "name": "Perth", "city": "Perth", "country": "Australia"},
    {"iata": "ADL", "name": "Adelaide", "city": "Adelaide", "country": "Australia"},
    {"iata": "OOL", "name": "Gold Coast", "city": "Gold Coast", "country": "Australia"},
    {"iata": "CNS", "name": "Cairns", "city": "Cairns", "country": "Australia"},
    {"iata": "DRW", "name": "Darwin International", "city": "Darwin", "country": "Australia"},
    {"iata": "AKL", "name": "Auckland", "city": "Auckland", "country": "New Zealand"},
    {"iata": "WLG", "name": "Wellington International", "city": "Wellington", "country": "New Zealand"},
    {"iata": "CHC", "name": "Christchurch International", "city": "Christchurch", "country": "New Zealand"},
    {"iata": "NAN", "name": "Nadi International", "city": "Nadi", "country": "Fiji"},

    # Africa
    {"iata": "CAI", "name": "Cairo International", "city": "Cairo", "country": "Egypt"},
    {"iata": "JNB", "name": "O. R. Tambo International", "city": "Johannesburg", "country": "South Africa"},
    {"iata": "CPT", "name": "Cape Town International", "city": "Cape Town", "country": "South Africa"},
    {"iata": "ADD", "name": "Bole International", "city": "Addis Ababa", "country": "Ethiopia"},
    {"iata": "NBO", "name": "Jomo Kenyatta International", "city": "Nairobi", "country": "Kenya"},
    {"iata": "LOS", "name": "Murtala Muhammed International", "city": "Lagos", "country": "Nigeria"},
    {"iata": "CMN", "name": "Mohammed V International", "city": "Casablanca", "country": "Morocco"},
    {"iata": "ALG", "name": "Houari Boumediene", "city": "Algiers", "country": "Algeria"},
    {"iata": "TUN", "name": "Tunis–Carthage International", "city": "Tunis", "country": "Tunisia"},
    {"iata": "DKR", "name": "Blaise Diagne International", "city": "Dakar", "country": "Senegal"},
    {"iata": "DAR", "name": "Julius Nyerere International", "city": "Dar es Salaam", "country": "Tanzania"},
    {"iata": "MRU", "name": "Sir Seewoosagur Ramgoolam International", "city": "Port Louis", "country": "Mauritius"},
    {"iata": "SEZ", "name": "Seychelles International", "city": "Mahé", "country": "Seychelles"},
]


def search_airports(q: str, limit: int = 10) -> list[dict[str, str]]:
    """Return up to `limit` airports matching the query string.

    Matching rules:
    - IATA code prefix match scores highest (e.g. "ha" → HAN, HAM, HAJ)
    - Substring match on city or airport name
    - Case-insensitive
    """
    if not q:
        return []

    q_norm = q.strip().lower()
    if not q_norm:
        return []

    iata_prefix: list[dict] = []
    city_match: list[dict] = []
    name_match: list[dict] = []
    seen: set[str] = set()

    for ap in AIRPORTS:
        iata_l = ap["iata"].lower()
        city_l = ap["city"].lower()
        name_l = ap["name"].lower()

        if iata_l.startswith(q_norm):
            if ap["iata"] not in seen:
                iata_prefix.append(ap)
                seen.add(ap["iata"])
        elif q_norm in city_l:
            if ap["iata"] not in seen:
                city_match.append(ap)
                seen.add(ap["iata"])
        elif q_norm in name_l:
            if ap["iata"] not in seen:
                name_match.append(ap)
                seen.add(ap["iata"])

    ordered = iata_prefix + city_match + name_match
    return ordered[: max(1, min(limit, 25))]
