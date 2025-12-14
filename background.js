const SERVER_URL = 'http://localhost:8765';

// Listen for messages from content script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'generateReply') {
    // Make request to local server
    fetch(`${SERVER_URL}/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        tweetText: request.tweetText,
        images: request.images,
        tone: request.tone
      })
    })
    .then(response => response.json())
    .then(data => {
      sendResponse(data);
    })
    .catch(error => {
      sendResponse({
        success: false,
        error: error.message
      });
    });

    return true; // Keep channel open for async response
  }

  if (request.action === 'checkHealth') {
    fetch(`${SERVER_URL}/health`)
      .then(r => r.json())
      .then(data => sendResponse(data))
      .catch(() => sendResponse({ status: 'error' }));

    return true;
  }
});

console.log('X Reply Generator background worker started');