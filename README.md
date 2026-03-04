# Clarion

Backend (Person A) + Frontend (Person B). Shared contract: `backend/app/models/schema.py`.

## Setup

- **Backend:** `cd backend && pip install -r ../requirements.txt && PYTHONPATH=. uvicorn app.main:app --reload`
- **Frontend:** `cd frontend && npm install && npm run dev`
- **Mock evidence:** Add test files under `mock-evidence/` (see README there).

## System Architecture

clarion/
├── README.md
├── .gitignore
├── requirements.txt
│
├── backend/
│   ├── app/
│   │   ├── main.py             
│   │   ├── config.py          
│   │   ├── models/
│   │   │   └── schema.py       
│   │   ├── routers/
│   │   │   ├── upload.py      
│   │   │   ├── generate.py
│   │   │   ├── edit.py  
│   │   │   └── export.py
│   │   ├── services/
│   │   │   ├── parser/         
│   │   │   │   ├── pdf.py
│   │   │   │   ├── audio.py
│   │   │   │   ├── image.py
│   │   │   │   └── labeler.py
│   │   │   ├── intelligence/  
│   │   │   │   ├── citations.py
│   │   │   │   ├── contradictions.py
│   │   │   │   └── missing_info.py
│   │   │   ├── video/          
│   │   │   │   ├── extractor.py
│   │   │   │   └── analyzer.py
│   │   │   └── generation/     
│   │   │       ├── report.py
│   │   │       ├── counter_args.py
│   │   │       ├── witness.py
│   │   │       └── export.py
│   │   └── utils/
│   │       └── storage.py       ← GCS upload/download helpers
│   └── tests/
│
├── frontend/                  
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── lib/
│   ├── package.json
│   └── tailwind.config.js
│
└── mock-evidence/               ← shared test data
    ├── police-report.pdf
    ├── medical-report.pdf
    ├── car-damage-1.jpg
    ├── car-damage-2.jpg
    ├── witness-audio.mp3
    └── dashcam.mp4