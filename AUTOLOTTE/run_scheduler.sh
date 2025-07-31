#!/bin/bash
cd /Users/ec2-user/yido/yidoweb/dbtest/AUTOLOTTE
source /Users/ec2-user/yido/yidoweb/dbtest/venv/bin/activate
export PYTHONPATH=/Users/ec2-user/yido/yidoweb/dbtest
export LOTTE_DB_URL=postgresql://test_user:0000@localhost:5432/my_test_db
export LOTTE_USER_ID=T301912
export LOTTE_PASSWORD=huixin210@
python scheduler.py
