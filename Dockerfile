FROM python:3.13-slim

WORKDIR /sleepy

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 9010

CMD ["python", "main.py"]