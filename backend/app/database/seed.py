from datetime import datetime, timezone

SERVICES = [
("POLICE_VERIFICATION","पोलीस व्हेरिफिकेशन (पोलीस पडताळणी)","Police Verification","पुलिस सत्यापन","Certificates"),
("CENTRAL_CASTE","केंद्रीय जात प्रमाणपत्र","Central Caste Certificate","केंद्रीय जाति प्रमाणपत्र","Certificates"),
("ITR","आयकर विवरणपत्र (ITR)","Income Tax Return (ITR)","आयकर रिटर्न (ITR)","Tax"),
("AFFIDAVIT","शपथपत्र (Affidavit)","Affidavit","शपथपत्र","Legal"),
("MARRIAGE_REGISTRATION","विवाह नोंदणी प्रमाणपत्र","Marriage Registration Certificate","विवाह पंजीकरण प्रमाणपत्र","Certificates"),
("LABOUR_CARD","लेबर कार्ड (कामगार कार्ड)","Labour Card","श्रमिक कार्ड","Schemes"),
("PM_VISHWAKARMA","पीएम विश्वकर्मा योजना","PM Vishwakarma Scheme","पीएम विश्वकर्मा योजना","Schemes"),
("PM_KISAN_NAMO","पीएम किसान / नमो शेतकरी योजना","PM Kisan / Namo Shetkari Scheme","पीएम किसान / नमो शेतकरी योजना","Schemes"),
("SHOP_ACT","दुकान परवाना (Shop Act)","Shop Act Licence","दुकान अधिनियम लाइसेंस","Business"),
("MSME","उद्योग (MSME) नोंदणी","MSME Registration","एमएसएमई पंजीकरण","Business"),
("FSSAI","फूड लायसन्स (FSSAI)","FSSAI Food Licence","एफएसएसएआई खाद्य लाइसेंस","Business"),
("GST_NEW","नवीन GST नोंदणी","New GST Registration","नया जीएसटी पंजीकरण","Tax"),
("E_SHRAM","ई-श्रम कार्ड","e-Shram Card","ई-श्रम कार्ड","Schemes"),
("AYUSHMAN","आयुष्मान भारत कार्ड","Ayushman Bharat Card","आयुष्मान भारत कार्ड","Schemes"),
("VOTER_ID","मतदार ओळखपत्र (Voter ID)","Voter ID","मतदाता पहचान पत्र","Identity"),
("PAN_CARD","पॅन कार्ड","PAN Card","पैन कार्ड","Identity"),
("SENIOR_CITIZEN","ज्येष्ठ नागरिक प्रमाणपत्र","Senior Citizen Certificate","वरिष्ठ नागरिक प्रमाणपत्र","Certificates"),
("DOMICILE","अधिवास प्रमाणपत्र (Domicile)","Domicile Certificate","अधिवास प्रमाणपत्र","Certificates"),
("NON_CREAMY_LAYER","नॉन-क्रिमिलेयर प्रमाणपत्र","Non-Creamy Layer Certificate","नॉन-क्रीमी लेयर प्रमाणपत्र","Certificates"),
("CASTE","जात प्रमाणपत्र","Caste Certificate","जाति प्रमाणपत्र","Certificates"),
("RESIDENCE","रहिवासी प्रमाणपत्र","Residence Certificate","निवास प्रमाणपत्र","Certificates"),
]

DOCUMENT_REQUIREMENTS = {
    "POLICE_VERIFICATION": ["आधार कार्ड", "रेशन कार्ड", "शाळा सोडल्याचा दाखला (टी.सी.)", "मतदान कार्ड", "दोन परिचित व्यक्तींची आधार कार्डे"],
    "CENTRAL_CASTE": ["मागील ३ वर्षांचे उत्पन्न प्रमाणपत्र", "प्रतिज्ञापत्र (Affidavit)", "जात प्रमाणपत्र", "आधार कार्ड", "फोटो व मोबाईल नंबर"],
    "ITR": ["पॅन कार्ड", "आधार कार्ड", "बँक खात्याची माहिती", "फॉर्म १६ / उत्पन्नाची माहिती"],
    "AFFIDAVIT": ["आधार कार्ड", "आवश्यक वैयक्तिक माहिती"],
    "MARRIAGE_REGISTRATION": ["वधू-वरांची आधार कार्डे", "तीन साक्षीदार व त्यांचे फोटो", "लग्नपत्रिका व लग्नाचे फोटो", "वधू-वरांचे चार पासपोर्ट आकाराचे फोटो", "साक्षीदारांची आधार कार्डे", "वधू-वरांचे टी.सी. (शाळा सोडल्याचे दाखले)", "इतर आवश्यक कागदपत्रे"],
    "LABOUR_CARD": ["आधार कार्ड", "बँक पासबुक", "फोटो", "कामाचा पुरावा"],
    "PM_VISHWAKARMA": ["आधार कार्ड", "पॅन कार्ड", "व्यवसायाची माहिती", "बँक पासबुक", "मोबाईल नंबर"],
    "PM_KISAN_NAMO": ["आधार कार्ड", "सातबारा उतारा (७/१२)", "आठ-अ उतारा (८-अ)", "फेरफार उतारा", "बँक पासबुक", "मोबाईल नंबर"],
    "SHOP_ACT": ["आधार कार्ड", "पॅन कार्ड", "फोटो", "दुकानाचा फोटो", "व्यवसायाच्या पत्त्याचा पुरावा"],
    "MSME": ["आधार कार्ड", "पॅन कार्ड", "व्यवसायाची माहिती", "मोबाईल नंबर"],
    "FSSAI": ["आधार कार्ड", "टॅक्स पावती", "फोटो", "दुकानाचा फोटो", "मोबाईल नंबर"],
    "GST_NEW": ["आधार कार्ड", "पॅन कार्ड", "फोटो", "बँक पासबुक / कॅन्सल चेक", "दुकानाचा भाडेकरार / मालकीचा पुरावा", "वीज बिल"],
    "E_SHRAM": ["आधार कार्ड", "बँक पासबुक", "मोबाईल नंबर"],
    "AYUSHMAN": ["आधार कार्ड", "मोबाईल नंबर"],
    "VOTER_ID": ["आधार कार्ड", "फोटो", "मोबाईल नंबर"],
    "PAN_CARD": ["आधार कार्ड", "दोन पासपोर्ट आकाराचे फोटो", "जन्म दाखला / इलेक्शन कार्ड / ड्रायव्हिंग लायसन्स", "मोबाईल नंबर", "ई-मेल आयडी"],
    "SENIOR_CITIZEN": ["आधार कार्ड", "जन्मतारखेचा पुरावा", "रेशन कार्ड", "फोटो"],
    "DOMICILE": ["आधार कार्ड", "जन्म दाखला / शाळा दाखला", "रहिवासी पुरावा"],
    "NON_CREAMY_LAYER": ["जात प्रमाणपत्र", "मागील ३ वर्षांचे उत्पन्न प्रमाणपत्र", "उत्पन्नाचे प्रतिज्ञापत्र", "आधार कार्ड", "फोटो"],
    "CASTE": ["आधार कार्ड", "कोतवाल बुकचा नक्कल उतारा", "खरेदी खत", "शाळा सोडल्याचा दाखला (टी.सी.)", "वडील / नातेवाईक यांचे जात प्रमाणपत्र (असल्यास)", "रेशन कार्ड", "अर्जदाराचा फोटो"],
    "RESIDENCE": ["आधार कार्ड", "वीज बिल", "रेशन कार्ड / घरपट्टी पावती", "मोबाईल नंबर", "अर्जदाराचा फोटो"],
}

FORM_REQUIREMENTS = {
    "CENTRAL_CASTE": ["मोबाईल नंबर"],
    "ITR": ["बँक खात्याची माहिती", "उत्पन्नाची माहिती"],
    "AFFIDAVIT": ["आवश्यक वैयक्तिक माहिती"],
    "PM_VISHWAKARMA": ["व्यवसायाची माहिती", "मोबाईल नंबर"],
    "PM_KISAN_NAMO": ["मोबाईल नंबर"],
    "MSME": ["व्यवसायाची माहिती", "मोबाईल नंबर"],
    "FSSAI": ["मोबाईल नंबर"],
    "E_SHRAM": ["मोबाईल नंबर"],
    "AYUSHMAN": ["मोबाईल नंबर"],
    "VOTER_ID": ["मोबाईल नंबर"],
    "PAN_CARD": ["मोबाईल नंबर", "ई-मेल आयडी"],
    "RESIDENCE": ["मोबाईल नंबर"],
}

SPLIT_REQUIREMENTS = {
    "CENTRAL_CASTE": {"फोटो व मोबाईल नंबर": ["फोटो"]},
    "ITR": {"फॉर्म १६ / उत्पन्नाची माहिती": ["फॉर्म १६"]},
}

def requirements_for(code):
    form_labels = FORM_REQUIREMENTS.get(code, [])
    split = SPLIT_REQUIREMENTS.get(code, {})
    documents = []
    for label in DOCUMENT_REQUIREMENTS[code]:
        if label in form_labels:
            continue
        documents.extend(split.get(label, [label]))
    document_requirements = [
        {"id": f"{code.lower()}-{index:02}", "label": {"mr": label}, "required": True}
        for index, label in enumerate(documents, 1)
    ]
    form_requirements = [
        {"id": f"{code.lower()}-field-{index:02}", "label": {"mr": label}, "required": True}
        for index, label in enumerate(form_labels, 1)
    ]
    return document_requirements, form_requirements

def seed_services(db):
    now = datetime.now(timezone.utc)
    for code, mr, en, hi, category in SERVICES:
        db.services.update_one(
            {"service_code": code},
            {"$setOnInsert": {
                "service_code": code,
                "name": {"mr": mr, "en": en, "hi": hi},
                "description": {"mr": "अर्जासाठी आवश्यक कागदपत्रांची यादी खाली दिली आहे. प्राधिकरणाच्या नियमानुसार अतिरिक्त कागदपत्रे लागू शकतात.",
                                "en": "The documents listed below are needed to apply. The responsible authority may require additional documents.",
                                "hi": "आवेदन के लिए आवश्यक दस्तावेज़ नीचे दिए गए हैं। संबंधित प्राधिकरण अतिरिक्त दस्तावेज़ मांग सकता है।"},
                "category": category,
                "document_requirements": requirements_for(code)[0],
                "form_requirements": requirements_for(code)[1],
                "checklist_review_required": False,
                "workflow_configuration": {},
                "is_published": True,
                "version": 1,
                "created_at": now,
                "updated_at": now,
                "updated_by": None
            }},
            upsert=True
        )
        service = db.services.find_one({"service_code": code})
        if service and service.get("checklist_review_required", True) and not service.get("document_requirements"):
            requirements, form_requirements = requirements_for(code)
            db.services.update_one(
                {"_id": service["_id"],
                 "document_requirements": service.get("document_requirements"),
                 "checklist_review_required": service.get("checklist_review_required", True)},
                {"$set": {
                    "description": {
                        "mr": "अर्जासाठी आवश्यक कागदपत्रांची यादी खाली दिली आहे. प्राधिकरणाच्या नियमानुसार अतिरिक्त कागदपत्रे लागू शकतात.",
                        "en": "The documents listed below are needed to apply. The responsible authority may require additional documents.",
                        "hi": "आवेदन के लिए आवश्यक दस्तावेज़ नीचे दिए गए हैं। संबंधित प्राधिकरण अतिरिक्त दस्तावेज़ मांग सकता है।",
                    },
                    "document_requirements": requirements,
                    "form_requirements": form_requirements,
                    "checklist_review_required": False,
                    "is_published": True,
                    "version": service.get("version", 1) + 1,
                    "updated_at": now,
                }},
            )
