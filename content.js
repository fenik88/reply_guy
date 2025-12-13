let webAppWindow = null;
let currentTone = 'bullish';

// Find or open web app
function getWebAppWindow() {
  // Try to find existing web app tab
  return new Promise((resolve) => {
    chrome.runtime.sendMessage({ action: 'findWebApp' }, (response) => {
      if (response && response.found) {
        resolve(true);
      } else {
        // Prompt user to open web app
        if (confirm('Please open the Web App first! Click OK to open it now.')) {
          window.open('about:blank', '_blank');
          alert('Paste the Web App URL in the new tab, then refresh X/Twitter');
        }
        resolve(false);
      }
    });
  });
}

// Add floating tone selector
function addToneSelector() {
  if (document.querySelector('.ai-tone-floating')) return;

  const toneBar = document.createElement('div');
  toneBar.className = 'ai-tone-floating';
  toneBar.innerHTML = `
    <div class="ai-tone-label">🎯 Reply Tone:</div>
    <select id="ai-global-tone" class="ai-tone-select-floating">
      <option value="bullish">Bullish</option>
      <option value="contrarian">Contrarian</option>
      <option value="curious">Curious</option>
      <option value="expert">Expert</option>
      <option value="hype">Hype</option>
      <option value="skeptical">Skeptical</option>
      <option value="funny">Funny</option>
      <option value="provocative">Provocative</option>
    </select>
  `;

  document.body.appendChild(toneBar);

  const selector = document.getElementById('ai-global-tone');
  selector.addEventListener('change', (e) => {
    currentTone = e.target.value;
    chrome.storage.local.set({ aiReplyTone: currentTone });
  });

  chrome.storage.local.get(['aiReplyTone'], (result) => {
    if (result.aiReplyTone) {
      currentTone = result.aiReplyTone;
      selector.value = currentTone;
    }
  });
}

// Extract images from tweet
function extractImages(tweet) {
  const images = [];
  const imgElements = tweet.querySelectorAll('img[src*="pbs.twimg.com"]');

  imgElements.forEach(img => {
    if (img.src && !img.src.includes('profile_images')) {
      images.push(img.src);
    }
  });

  return images;
}

// Send message to web app
function sendToWebApp(tweetText, images) {
  return new Promise((resolve, reject) => {
    const messageId = Date.now() + Math.random();

    // Listen for response
    const handleResponse = (event) => {
      if (event.data.type === 'REPLY_GENERATED' && event.data.messageId === messageId) {
        window.removeEventListener('message', handleResponse);
        if (event.data.success) {
          resolve(event.data.reply);
        } else {
          reject(new Error(event.data.error || 'Generation failed'));
        }
      }
    };

    window.addEventListener('message', handleResponse);

    // Send to all tabs (web app will receive it)
    window.postMessage({
      type: 'GENERATE_REPLY',
      messageId: messageId,
      tweetText: tweetText,
      images: images,
      tone: currentTone
    }, '*');

    // Also broadcast to potential parent windows
    if (window.opener) {
      window.opener.postMessage({
        type: 'GENERATE_REPLY',
        messageId: messageId,
        tweetText: tweetText,
        images: images,
        tone: currentTone
      }, '*');
    }

    // Timeout after 15 seconds
    setTimeout(() => {
      window.removeEventListener('message', handleResponse);
      reject(new Error('Timeout - is the Web App open?'));
    }, 15000);
  });
}

// Add generate buttons to tweets
function addGenerateButtons() {
  const tweets = document.querySelectorAll('article[data-testid="tweet"]');

  tweets.forEach(tweet => {
    if (tweet.querySelector('.ai-generate-btn')) return;

    const actionBar = tweet.querySelector('[role="group"]');
    if (!actionBar) return;

    const btn = document.createElement('button');
    btn.className = 'ai-generate-btn';
    btn.innerHTML = '✨ Generate';

    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      e.preventDefault();

      if (btn.disabled) return;

      btn.disabled = true;
      btn.innerHTML = '⏳ Generating...';

      try {
        const tweetText = tweet.querySelector('[data-testid="tweetText"]')?.innerText || '';
        const images = extractImages(tweet);

        // Click reply button to open reply box
        const replyBtn = tweet.querySelector('[data-testid="reply"]');
        if (replyBtn && !document.querySelector('[data-testid="tweetTextarea_0"]')) {
          replyBtn.click();
          await new Promise(resolve => setTimeout(resolve, 800));
        }

        // Send to web app
        const reply = await sendToWebApp(tweetText, images);

        // Paste reply
        const replyBox = document.querySelector('[data-testid="tweetTextarea_0"]');
        if (replyBox) {
          replyBox.focus();
          replyBox.textContent = '';
          document.execCommand('insertText', false, reply);
          replyBox.dispatchEvent(new Event('input', { bubbles: true }));

          btn.innerHTML = '✅ Pasted!';
          setTimeout(() => {
            btn.innerHTML = '✨ Generate';
            btn.disabled = false;
          }, 2000);
        } else {
          throw new Error('Reply box not found');
        }

      } catch (error) {
        console.error('Error:', error);
        btn.innerHTML = '❌ ' + (error.message.includes('Timeout') ? 'Open Web App!' : 'Error');
        setTimeout(() => {
          btn.innerHTML = '✨ Generate';
          btn.disabled = false;
        }, 3000);
      }
    });

    actionBar.appendChild(btn);
  });
}

// Initialize
setTimeout(() => {
  addToneSelector();
  addGenerateButtons();
}, 1000);

// Watch for new tweets
const observer = new MutationObserver(() => {
  addToneSelector();
  addGenerateButtons();
});

observer.observe(document.body, {
  childList: true,
  subtree: true
});

// Ping web app on load
window.postMessage({ type: 'PING' }, '*');