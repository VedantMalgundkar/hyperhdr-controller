import os
import subprocess
from flask import Flask, jsonify, request, render_template
from flask_socketio import SocketIO, emit

from app import create_app
from app.routes.hyperhdr_install import hyperhdr_install_bp
from app.routes.led import led_bp

from app.services.led_commands import check_input_signal

app = create_app()

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Register blueprints
app.register_blueprint(hyperhdr_install_bp, url_prefix="/hyperhdr")
app.register_blueprint(led_bp, url_prefix="/led")

@app.route("/")
def health_check():
    return jsonify(status="OK", message="Service is healthy"), 200

@app.route('/home')
def main():
    return """
    <!DOCTYPE html>
<html lang="en">
  <head>
<meta http-equiv="Cache-control" content="no-cache" charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/3.0.4/socket.io.js" integrity="sha512-aMGMvNYu8Ue4G+fHa359jcPb1u+ytAF+P2SCb+PxrjCdO3n3ZTxJ30zuH39rimUggmTwmh2u7wvQsDTHESnmfQ==" crossorigin="anonymous"></script>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-EVSTQN3/azprG1Anm3QDgpJLIm9Nao0Yz1ztcQTwFspd3yD65VohhpuuCOmLASjC" crossorigin="anonymous">
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/js/bootstrap.bundle.min.js" integrity="sha384-MrcW6ZMFYlzcLA8Nl+NtUVF0sA7MsXsP1UyJoMp4YLEuNSfAP+JcXn/tWtIaxVXM" crossorigin="anonymous"></script>
<script type="text/javascript" src="//code.jquery.com/jquery-1.4.2.min.js"></script>
<style>
.navbar-brand {
font-family: 'Merriweather';
font-size: 30px;
}
.inner {
text-align: center;
margin: auto;
margin-top: 10px;
padding: 10px;
border-style: solid;
width: 50%;
color: black;

}
</style>
</head>

<body>
<nav class="navbar navbar-expand-lg navbar-dark bg-dark">
  <div class="container">
   <a class="navbar-brand" href={{ url_for('main') }}>Flask</a>
    <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNavDropdown" aria-controls="navbarNavDropdown" aria-expanded="false" aria-label="Toggle navigation">
      <span class="navbar-toggler-icon"></span>
    </button>
  </div>
</nav>
<div class="container">
<div class="inner">
 <div id="header"></div><br>
<button class="btn btn-primary" id="checkbutton" onClick="myupdate()">Submit</button>
<div id="demo"></div>
</div>
</div>
<script>
const socket = io(); //socketio connection to server//
socket.on("connect", () => {
 console.log("connected");
        document.getElementById("header").innerHTML = "<h3>" + "Websocket Connected" + "</h3";
});

socket.on("disconnect", () => {
 console.log("disconnected");
        document.getElementById("header").innerHTML = "<h3>" + "Websocket Disconnected" + "</h3>";
});

function myupdate() {
  //Event sent by Client
 socket.emit("my_event", function() {
 });
}

// Event sent by Server//
socket.on("server", function(msg) {
        let myvar = JSON.parse(msg.data1);
        //Check if entire data is sent by server//
        if (myvar == "4") {
                document.getElementById("demo").innerHTML = "";
                document.querySelector('#checkbutton').innerText = "Submit";
                document.getElementById("checkbutton").style.cursor = "pointer";
                document.getElementById("checkbutton").disabled = false;
                document.getElementById("checkbutton").className = "btn btn-primary";
 
        }

        else {
                document.getElementById("demo").innerHTML += msg.data + "<br>";
                document.getElementById("checkbutton").disabled = true;
                document.getElementById("checkbutton").innerHTML = "Loading..";
                document.getElementById("checkbutton").style.cursor = "not-allowed";
                document.getElementById("checkbutton").style.pointerEvents = "auto";
        }
});

</script>
</body>
</html>
    """

@socketio.on("my_event")
def checkping():
    sid = request.sid
    for x in range(5):
        cmd = 'ping -c 1 8.8.8.8 | head -2 | tail -1'
        listing1 = subprocess.run(cmd, stdout=subprocess.PIPE, text=True, shell=True)
        emit('server', {"data1": x, "data": listing1.stdout}, room=sid)
        socketio.sleep(1)


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
