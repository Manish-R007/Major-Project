"""
Seed catalogue of government schemes the DSS can recommend to FRA
patta holders. Eligibility rules are intentionally simple/explicit so
they're easy to audit and extend — this is a rule engine, not a model.
"""

SCHEMES = [
    {
        "name": "PM-KISAN (Pradhan Mantri Kisan Samman Nidhi)",
        "ministry": "Ministry of Agriculture & Farmers Welfare",
        "description": "Income support of ₹6,000/year to small and marginal landholding farmer families.",
        "eligibility_rules": {
            "claim_types": ["IFR"],
            "land_types": ["cultivable"],
            "min_area": 0.1,
            "max_area": 5.0,
        },
    },
    {
        "name": "Jal Jeevan Mission",
        "ministry": "Ministry of Jal Shakti",
        "description": "Provides functional household tap water connections, prioritizing tribal and forest-fringe habitations.",
        "eligibility_rules": {
            "claim_types": ["IFR", "CFR", "CR"],
            "land_types": ["homestead", "cultivable", "waterlogged"],
            "min_area": 0.0,
        },
    },
    {
        "name": "MGNREGA (Mahatma Gandhi National Rural Employment Guarantee Act)",
        "ministry": "Ministry of Rural Development",
        "description": "Guarantees 100 days of wage employment per year, including land/water development works on FRA land.",
        "eligibility_rules": {
            "claim_types": ["IFR", "CFR", "CR"],
            "land_types": ["cultivable", "forest", "homestead"],
            "min_area": 0.0,
        },
    },
    {
        "name": "Van Dhan Vikas Yojana",
        "ministry": "Ministry of Tribal Affairs",
        "description": "Supports value-addition and marketing of Minor Forest Produce (MFP) through tribal SHGs/clusters.",
        "eligibility_rules": {
            "claim_types": ["CFR", "CR"],
            "land_types": ["forest"],
            "min_area": 0.0,
        },
    },
    {
        "name": "Pradhan Mantri Awas Yojana - Gramin (PMAY-G)",
        "ministry": "Ministry of Rural Development",
        "description": "Financial assistance for construction of pucca houses for eligible rural households, including FRA homestead holders.",
        "eligibility_rules": {
            "claim_types": ["IFR"],
            "land_types": ["homestead"],
            "min_area": 0.0,
            "max_area": 2.0,
        },
    },
    {
        "name": "Deendayal Antyodaya Yojana - NRLM",
        "ministry": "Ministry of Rural Development",
        "description": "Promotes self-help groups and livelihood diversification for rural poor, including forest-dependent tribal households.",
        "eligibility_rules": {
            "claim_types": ["IFR", "CFR", "CR"],
            "land_types": ["cultivable", "forest", "homestead", "waterlogged"],
            "min_area": 0.0,
        },
    },
    {
        "name": "Compensatory Afforestation Fund (CAMPA) - Community Works",
        "ministry": "Ministry of Environment, Forest and Climate Change",
        "description": "Funds afforestation, soil & water conservation, and forest protection works benefiting CFR/CR title holders.",
        "eligibility_rules": {
            "claim_types": ["CFR", "CR"],
            "land_types": ["forest"],
            "min_area": 1.0,
        },
    },
]
