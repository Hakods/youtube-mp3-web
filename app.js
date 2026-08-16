const API_BASE_URL = 'https://hakods-youtube-mp3.onrender.com';

const form = document.getElementById('download-form');
const button = document.getElementById('submit-button');
const status = document.getElementById('status');

function setStatus(message, type = '') {
  status.textContent = message;
  status.className = `status ${type}`.trim();
}

function getFilename(response) {
  const disposition = response.headers.get('content-disposition') || '';
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch (_) {}
  }

  const plainMatch = disposition.match(/filename="?([^";]+)"?/i);
  return plainMatch ? plainMatch[1] : 'youtube-download';
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();

  const url = document.getElementById('url').value.trim();
  const password = document.getElementById('password').value;

  if (!url) return;

  button.disabled = true;
  button.textContent = 'Hazırlanıyor…';
  setStatus('Ses indiriliyor ve MP3 formatına dönüştürülüyor. Playlistlerde bu işlem biraz sürebilir.');

  const data = new FormData();
  data.append('url', url);
  data.append('password', password);

  try {
    const response = await fetch(`${API_BASE_URL}/download`, {
      method: 'POST',
      body: data,
    });

    if (!response.ok) {
      let message = `Sunucu hatası (${response.status})`;
      try {
        const body = await response.json();
        if (body.detail) message = body.detail;
      } catch (_) {}
      throw new Error(message);
    }

    const blob = await response.blob();
    const filename = getFilename(response);
    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = objectUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(objectUrl);

    setStatus('Hazır. Dosya indirme işlemi başlatıldı.', 'success');
  } catch (error) {
    setStatus(error.message || 'İndirme sırasında bir hata oluştu.', 'error');
  } finally {
    button.disabled = false;
    button.textContent = 'MP3 İndir';
  }
});
