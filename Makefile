install:
	virtualenv --python python3 venv
	venv/bin/pip install --upgrade pip &&\
		venv/bin/pip install -r requirements.txt
