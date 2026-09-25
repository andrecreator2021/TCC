# App de PTS — Backend em Python

Versão do projeto com **backend em Python (Flask)** no lugar do banco de dados exclusivo do Claude. O front-end continua sendo HTML/CSS/JavaScript (é o único jeito de um navegador funcionar), mas agora ele conversa com um servidor Python de verdade, que guarda os dados em **SQLite**, gera o **PDF em Python** (reportlab) e envia **e-mail e WhatsApp automaticamente** pelo servidor.

## Estrutura do projeto

```
pts-backend/
  app.py             ← servidor Flask: rotas da API + banco de dados
  pdf_generator.py   ← geração do PDF da PTS (reportlab)
  sender.py          ← envio de e-mail (smtplib) e WhatsApp (Twilio)
  requirements.txt   ← dependências Python
  .env.example        ← modelo de configuração (copie para ".env")
  static/
    index.html        ← front-end (HTML/CSS/JS), servido pelo Flask
  pts.db               ← banco SQLite (criado automaticamente na 1ª execução)
```

## Passo a passo no VS Code

1. Abra a pasta `pts-backend` no VS Code (**Arquivo → Abrir Pasta**)
2. Abra um terminal integrado (**Terminal → Novo Terminal**)
3. Crie um ambiente virtual e ative:
   ```bash
   python3 -m venv venv
   source venv/bin/activate        # Windows: venv\Scripts\activate
   ```
4. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
5. Copie o arquivo de configuração e preencha suas credenciais:
   ```bash
   cp .env.example .env
   ```
   Edite o `.env` com seu servidor SMTP (para e-mail) e/ou suas credenciais do Twilio (para WhatsApp) — veja os comentários dentro do próprio arquivo. **Sem preencher isso, o app funciona normalmente (criar, listar, encerrar, gerar PDF); só o botão "Enviar" vai retornar erro.**
6. Rode o servidor:
   ```bash
   python app.py
   ```
7. Abra **http://localhost:5000** no navegador — é o mesmo app de antes, agora servido pelo Python

## O que mudou em relação à versão anterior (Claude / JS)

| Antes | Agora |
|---|---|
| Dados salvos em `window.storage` (só existe no Claude) | Dados salvos em **SQLite** via Flask |
| PDF gerado no navegador (jsPDF) | PDF gerado no **servidor** (reportlab) |
| "Enviar" baixava o PDF e abria mailto:/wa.me — usuário anexava manualmente | **Backend envia automaticamente**: e-mail com anexo real (smtplib) e WhatsApp com mídia (Twilio) |
| Front-end 100% autônomo (1 arquivo HTML) | Front-end (`static/index.html`) + backend Python trocando dados via `fetch()` |

## Notas importantes

- **E-mail**: funciona imediatamente após configurar `SMTP_HOST/USER/PASS` no `.env` — com Gmail, use uma ["senha de app"](https://myaccount.google.com/apppasswords), não a senha normal da conta.
- **WhatsApp**: precisa de uma conta Twilio (tem sandbox gratuito para testes) e, para anexar o PDF, o Twilio precisa conseguir *baixar* o arquivo de uma URL pública — em teste local isso exige um túnel (ex: [ngrok](https://ngrok.com)); publicado num servidor real, o próprio domínio já resolve isso. Isso está documentado no `.env.example` e é uma limitação da própria plataforma do WhatsApp, não do código.
- O banco de dados é um único arquivo `pts.db` — para reiniciar do zero, basta apagá-lo (ele é recriado automaticamente ao rodar `python app.py` de novo).
- Este backend já foi testado ponta a ponta (criar PTS → listar → gerar PDF → encerrar → gerar PDF final) antes da entrega.
