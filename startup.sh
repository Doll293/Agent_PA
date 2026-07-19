#!/bin/bash
python -m streamlit run mail_manager/streamlit_app.py \
    --server.port=8000 \
    --server.address=0.0.0.0
