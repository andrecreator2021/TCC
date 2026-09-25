"""
Envio da PTS por e-mail e WhatsApp.

E-mail: usa smtplib (biblioteca padrão do Python) — funciona imediatamente,
sem dependências externas, desde que você configure um servidor SMTP no .env
(ex: Gmail com "senha de app", ou qualquer outro provedor).

WhatsApp: usa a API do Twilio, que exige uma conta (tem sandbox gratuito para
testes) e, para anexar o PDF, exige que o arquivo esteja acessível por uma URL
pública (o Twilio busca o arquivo nessa URL) — em desenvolvimento local isso
normalmente requer um túnel público (ex: ngrok); em produção, o próprio domínio
do servidor já resolve isso.
"""
import os
import smtplib
from email.message import EmailMessage


def enviar_email(destinatario: str, assunto: str, corpo: str, pdf_bytes: bytes, pdf_filename: str):
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASS"]
    remetente = os.environ.get("SMTP_FROM", user)

    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = remetente
    msg["To"] = destinatario
    msg.set_content(corpo)
    msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=pdf_filename)

    with smtplib.SMTP(host, port, timeout=20) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(msg)


def enviar_whatsapp(numero_destino: str, mensagem: str, media_url: str = None):
    # import feito aqui dentro para que o app funcione mesmo sem a lib "twilio"
    # instalada, caso a pessoa só queira usar o envio por e-mail
    from twilio.rest import Client

    sid = os.environ["TWILIO_ACCOUNT_SID"]
    token = os.environ["TWILIO_AUTH_TOKEN"]
    remetente = os.environ["TWILIO_WHATSAPP_FROM"]  # ex: 'whatsapp:+14155238886' (sandbox)

    digitos = "".join(ch for ch in numero_destino if ch.isdigit())
    if len(digitos) <= 11:
        digitos = "55" + digitos  # assume Brasil se não vier com código de país

    client = Client(sid, token)
    kwargs = {"from_": remetente, "to": f"whatsapp:+{digitos}", "body": mensagem}
    if media_url:
        kwargs["media_url"] = [media_url]
    client.messages.create(**kwargs)
