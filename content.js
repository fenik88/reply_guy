let currentTone = 'bullish';

function addToneSelector() {
  if (document.querySelector('.ai-tone-floating')) return;

  const toneBar = document.createElement('div');
  toneBar.className = 'ai-tone-floating';
  toneBar.innerHTML = `
    <div class="ai-tone-label">🎯 Tone:</div>
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
  });
}

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

function generateReply(tweetText, images) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(
      {
        action: 'generateReply',
        tweetText: tweetText,
        images: images,
        tone: currentTone
      },
      (response) => {
        if (response.success) {
          resolve(response.reply);
        } else {
          reject(new Error(response.error || 'Failed to generate'));
        }
      }
    );
  });
}

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

        // Open reply box
        const replyBtn = tweet.querySelector('[data-testid="reply"]');
        if (replyBtn && !document.querySelector('[data-testid="tweetTextarea_0"]')) {
          replyBtn.click();
          await new Promise(resolve => setTimeout(resolve, 800));
        }

        // Generate reply via background worker
        const reply = await generateReply(tweetText, images);

        // Paste it
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
        const isServerDown = error.message.includes('Failed to fetch') || error.message.includes('Server');
        btn.innerHTML = '❌ ' + (isServerDown ? 'Server Down!' : 'Error');
        setTimeout(() => {
          btn.innerHTML = '✨ Generate';
          btn.disabled = false;
        }, 3000);
      }
    });

    actionBar.appendChild(btn);
  });
}

// Check server health on load
chrome.runtime.sendMessage({ action: 'checkHealth' }, (response) => {
  if (response && response.status === 'ok') {
    console.log('✅ X Reply Generator server connected');
  } else {
    console.warn('⚠️ X Reply Generator server not running. Start the Python server!');
  }
});

setTimeout(() => {
  addToneSelector();
  addGenerateButtons();
}, 1000);

const observer = new MutationObserver(() => {
  addToneSelector();
  addGenerateButtons();
});

observer.observe(document.body, {
  childList: true,
  subtree: true
});