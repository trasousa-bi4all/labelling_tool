from fastapi import FastAPI, Depends, status, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_login import LoginManager  # Loginmanager Class
from fastapi_login.exceptions import InvalidCredentialsException  # Exception class
from fastapi.templating import Jinja2Templates
from fastapi.middleware.wsgi import WSGIMiddleware
import os
from pathlib import Path
from utils import *
import uvicorn
from dashapp import create_dash_app

app = FastAPI()
db = redis_db()


SECRET = "secret-key"
# To obtain a suitable secret key you can run | import os; print(os.urandom(24).hex())
BASE_PATH = Path(__file__).parent.resolve()
templates = Jinja2Templates(directory=os.path.join(BASE_PATH, "templates"))

manager = LoginManager(SECRET, token_url="/auth/login", use_cookie=True)
manager.cookie_name = "some-name"


@manager.user_loader()
def load_user_pwd(username: str):
    try:
        pwd = db.get_pwd(username)
    except:
        raise InvalidCredentialsException
    return pwd


@app.post("/auth/login")
def login(data: OAuth2PasswordRequestForm = Depends()):
    username = data.username
    password = data.password
    if password != load_user_pwd(username):
        raise InvalidCredentialsException
    access_token = manager.create_access_token(data={"sub": username})
    resp = RedirectResponse(url="/private", status_code=status.HTTP_302_FOUND)
    manager.set_cookie(resp, access_token)
    return resp


@app.get("/", response_class=HTMLResponse)
def loginwithCreds(request: Request):
    with open(os.path.join(BASE_PATH, "templates/login.html")) as f:
        return HTMLResponse(content=f.read())


# This code has to change probabli change
# fastapi app to flask so it matches the dash system
@app.get("/private")
def get_user(user=Depends(manager)):
    dash_app = create_dash_app(requests_pathname_prefix="/dash/", username=user)
    app.mount("/dash", WSGIMiddleware(dash_app.server))
    resp = RedirectResponse(url="/dash", status_code=status.HTTP_302_FOUND)
    return resp


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
