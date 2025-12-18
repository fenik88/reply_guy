let currentTone = 'bullish';

function safeRuntimeSendMessage(payload) {
  return new Promise((resolve, reject) => {
    try {
      if (!chrome || !chrome.runtime || !chrome.runtime.id) {
        reject(new Error('Extension context invalidated'));
        return;
      }

      chrome.runtime.sendMessage(payload, (response) => {
        const err = chrome.runtime.lastError;
        if (err) {
          reject(new Error(err.message || 'Runtime error'));
          return;
        }
        resolve(response);
      });
    } catch (e) {
      reject(e);
    }
  });
}

function isContextInvalidatedError(message) {
  const m = (message || '').toLowerCase();
  return m.includes('extension context invalidated') || m.includes('context invalidated');
}

// Check if we're on a tweet detail page (in comments) or in feed
function isInTweetDetailPage() {
  return window.location.pathname.includes('/status/');
}

function getXComposerEditable(root = document) {
  // Prefer currently focused editable textbox
  const active = document.activeElement;
  if (active && active.getAttribute) {
    const ce = active.getAttribute('contenteditable');
    const role = active.getAttribute('role');
    if (ce === 'true' && role === 'textbox') return active;
  }

  // Prefer reply dialog composer
  const dialog = root.querySelector?.('[role="dialog"]') || root;

  // X sometimes wraps the contenteditable inside tweetTextarea_0
  const inner = dialog.querySelector?.('[data-testid="tweetTextarea_0"] [role="textbox"][contenteditable="true"]')
    || dialog.querySelector?.('[data-testid="tweetTextarea_0"] [contenteditable="true"]');
  if (inner) return inner;

  // Or tweetTextarea_0 itself may be the textbox
  const outer = dialog.querySelector?.('[data-testid="tweetTextarea_0"][role="textbox"][contenteditable="true"]')
    || dialog.querySelector?.('[data-testid="tweetTextarea_0"][contenteditable="true"]');
  if (outer) return outer;

  // Fallback: any textbox
  return dialog.querySelector?.('[role="textbox"][contenteditable="true"][aria-label]')
    || dialog.querySelector?.('[role="textbox"][contenteditable="true"]');
}

function dispatchPaste(editable, text) {
  try {
    const dt = new DataTransfer();
    dt.setData('text/plain', text);

    const ev = new ClipboardEvent('paste', {
      bubbles: true,
      cancelable: true,
      clipboardData: dt
    });

    return editable.dispatchEvent(ev);
  } catch (_) {
    return false;
  }
}

// Insert text into X editor in a way that updates internal state
async function pasteIntoXEditor(replyBox, text) {
  const dialogRoot = document.querySelector('[role="dialog"]') || document;
  const editable = getXComposerEditable(dialogRoot) || replyBox;

  // Ensure focus on the real editable node
  try { editable.focus(); } catch (_) {}
  try { editable.click(); } catch (_) {}

  // Let X mount/update
  await new Promise(r => requestAnimationFrame(r));

  // Try paste event (best for X/Lexical to update internal state)
  const pasted = dispatchPaste(editable, text);

  // Fallback ONLY if paste fails
  if (!pasted) {
    try {
      document.execCommand('insertText', false, text);
    } catch (_) {}
  }

  // Fire input to notify frameworks
  try {
    editable.dispatchEvent(new InputEvent('input', {
      bubbles: true,
      inputType: 'insertFromPaste',
      data: text,
      composed: true
    }));
  } catch (_) {
    try { editable.dispatchEvent(new Event('input', { bubbles: true })); } catch (_) {}
  }

  // Nudge editor to allow further typing
  try {
    editable.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', bubbles: true }));
    editable.dispatchEvent(new KeyboardEvent('keyup', { key: ' ', bubbles: true }));
  } catch (_) {}

  // Caret to end inside text node
  try {
    const sel = window.getSelection();
    if (sel && editable.firstChild) {
      const range = document.createRange();
      range.setStart(editable.firstChild, editable.firstChild.length || 0);
      range.collapse(true);
      sel.removeAllRanges();
      sel.addRange(range);
    }
  } catch (_) {}
}

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
  return safeRuntimeSendMessage({
    action: 'generateReply',
    tweetText: tweetText,
    images: images,
    tone: currentTone
  }).then((response) => {
    if (response && response.success) {
      return response.reply;
    }
    throw new Error((response && response.error) || 'Failed to generate');
  });
}

// NEW: Navigate to tweet's comment section
function navigateToTweetComments(tweet) {
  return new Promise((resolve, reject) => {
    try {
      // Find the tweet link (timestamp link that goes to tweet detail)
      const timeLink = tweet.querySelector('time')?.parentElement;
      
      if (timeLink && timeLink.href) {
        // Navigate to the tweet detail page
        window.location.href = timeLink.href;
        resolve();
      } else {
        reject(new Error('Could not find tweet link'));
      }
    } catch (e) {
      reject(e);
    }
  });
}

// Check for pending reply after navigation
async function checkPendingReply() {
  const pendingData = sessionStorage.getItem('x_reply_pending');
  
  if (pendingData) {
    try {
      const data = JSON.parse(pendingData);
      
      // Check if data is recent (within last 10 seconds)
      if (Date.now() - data.timestamp < 10000) {
        console.log('🔄 Resuming reply generation after navigation...');
        
        // Clear the pending data
        sessionStorage.removeItem('x_reply_pending');
        
        // Wait for page to load
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        // Find and click reply button to open reply box
        const mainTweet = document.querySelector('article[data-testid="tweet"]');
        if (mainTweet) {
          const replyBtn = mainTweet.querySelector('[data-testid="reply"]');
          if (replyBtn) {
            replyBtn.click();
            await new Promise(resolve => setTimeout(resolve, 1400));
          }
        }
        
        // Generate reply with stored data
        currentTone = data.tone || 'bullish';
        const reply = await generateReply(data.tweetText, data.images);
        
        // Paste it
        const dialogRoot = document.querySelector('[role="dialog"]') || document;
        const replyBox = getXComposerEditable(dialogRoot);
        
        if (replyBox) {
          await pasteIntoXEditor(replyBox, reply);
          console.log('✅ Reply generated and pasted after navigation!');
        }
      } else {
        // Data too old, clear it
        sessionStorage.removeItem('x_reply_pending');
      }
    } catch (e) {
      console.error('Error processing pending reply:', e);
      sessionStorage.removeItem('x_reply_pending');
    }
  }
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

        const isDetailPage = isInTweetDetailPage();

        if (!isDetailPage) {
          // We're in the feed - need to navigate to comments first
          btn.innerHTML = '🔄 Opening comments...';
          
          // Store the data to generate after reload
          sessionStorage.setItem('x_reply_pending', JSON.stringify({
            tweetText: tweetText,
            images: images,
            tone: currentTone,
            timestamp: Date.now()
          }));
          
          // Navigate to tweet detail page
          await navigateToTweetComments(tweet);
          
          // Navigation will happen, button state doesn't matter
          return;
        }

        // We're already on tweet detail page - generate and paste
        // Open reply box
        const replyBtn = tweet.querySelector('[data-testid="reply"]');
        const dialogRoot = () => document.querySelector('[role="dialog"]') || document;
        if (replyBtn && !getXComposerEditable(dialogRoot())) {
          replyBtn.click();
          await new Promise(resolve => setTimeout(resolve, 1400));
        }

        // Generate reply via background worker
        const replyBox = getXComposerEditable(dialogRoot()) || document.querySelector('[role="dialog"] [data-testid="tweetTextarea_0"]') || document.querySelector('[data-testid="tweetTextarea_0"]');
        const reply = await generateReply(tweetText, images);

        // Paste it
        if (replyBox) {
          await pasteIntoXEditor(replyBox, reply);

          const editable = getXComposerEditable(dialogRoot()) || replyBox;
          const hasText = (((editable.innerText || editable.textContent || '')).trim().length > 0);

          if (!hasText) {
            try { await navigator.clipboard.writeText(reply); } catch (_) {}
            btn.innerHTML = '📋 Copied — Paste to edit';
          } else {
            btn.innerHTML = '✅ Pasted!';
          }
          setTimeout(() => {
            btn.innerHTML = '✨ Generate';
            btn.disabled = false;
          }, 2000);
        } else {
          throw new Error('Reply box not found');
        }

      } catch (error) {
        console.error('Error:', error);
        const msg = error && error.message ? error.message : String(error);
        const isInvalidated = isContextInvalidatedError(msg);
        const isServerDown = msg.includes('Failed to fetch') || msg.includes('Server');
        btn.innerHTML = '❌ ' + (isInvalidated ? 'Reload Extension' : (isServerDown ? 'Server Down!' : 'Error'));
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
safeRuntimeSendMessage({ action: 'checkHealth' })
  .then((response) => {
    if (response && response.status === 'ok') {
      console.log('✅ X Reply Generator server connected');
    } else {
      console.warn('⚠️ X Reply Generator server not running. Start the Python server!');
    }
  })
  .catch((err) => {
    const msg = err && err.message ? err.message : String(err);
    if (isContextInvalidatedError(msg)) {
      console.warn('⚠️ Extension context invalidated (likely extension reloaded). Refresh the page.');
    } else {
      console.warn('⚠️ Health check failed:', msg);
    }
  });

setTimeout(() => {
  addToneSelector();
  addGenerateButtons();
  checkPendingReply(); // Check if we need to resume generation
}, 1000);

const observer = new MutationObserver(() => {
  addToneSelector();
  addGenerateButtons();
});

observer.observe(document.body, {
  childList: true,
  subtree: true
});