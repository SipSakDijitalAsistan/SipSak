const recordButton = document.getElementById('record-button');
const messageInput = document.getElementById('message');
const avatarVideo = document.getElementById('avatar-video');
let mediaRecorder;
let audioChunks = [];

recordButton.addEventListener('mousedown', startRecording);
recordButton.addEventListener('mouseup', stopRecording);
recordButton.addEventListener('mouseleave', stopRecording);

function startRecording() {
    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
            mediaRecorder.start();

            mediaRecorder.addEventListener("dataavailable", event => {
                audioChunks.push(event.data);
            });

            recordButton.textContent = 'Konuşuyor...';
        });
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state === "recording") {
        mediaRecorder.stop();
        recordButton.textContent = 'Konuş';

        mediaRecorder.addEventListener("stop", () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            sendAudioToServer(audioBlob);
            audioChunks = [];
        });
    }
}

function sendAudioToServer(audioBlob) {
    const formData = new FormData();
    formData.append("audio", audioBlob, "recording.webm");

    fetch('/speech-to-text', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.text) {
            messageInput.value = data.text;
            sendMessage();
        } else {
            console.error('Speech recognition failed:', data.error);
            alert("Konuşma tanınamadı. Lütfen tekrar deneyin.");
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert("Ses tanıma işlemi sırasında bir hata oluştu.");
    });
}

function sendMessage() {
    const message = messageInput.value;
    if (!message.trim()) return;

    messageInput.value = '';
    displayMessage(message, 'user');

    fetch('/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ message: message })
    })
    .then(response => response.json())
.then(data => {
    displayMessage(data.response, data.sender);
    if (data.audio_file) {
        playAudioWithAnimation(data.audio_file);
    }
});
}

function displayMessage(message, sender) {
    const messagesDiv = document.getElementById('messages');
    const messageDiv = document.createElement('div');
    messageDiv.textContent = message;
    messageDiv.className = `message ${sender}-message`;
    messagesDiv.appendChild(messageDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

messageInput.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

function startVideoAnimation() {
    avatarVideo.play();
}

function stopVideoAnimation() {
    avatarVideo.pause();
    avatarVideo.currentTime = 0;
}

function playAudioWithAnimation(audioFile) {
    const audioPlayer = document.getElementById('audio-player');
    audioPlayer.src = "/audio/" + audioFile;

    audioPlayer.onplay = startVideoAnimation;
    audioPlayer.onended = stopVideoAnimation;
    audioPlayer.onpause = stopVideoAnimation;

    audioPlayer.play();
}