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

// Check if a reply dialog is actually open (not the main compose dialog)
function isReplyDialogOpen() {
  const dialog = document.querySelector('[role="dialog"]');
  if (!dialog) return false;
  
  // Reply dialogs usually have "Replying to" text
  const replyingTo = dialog.querySelector('[data-testid="reply-to"]');
  if (replyingTo) return true;
  
  // Or check for the reply context text
  const hasReplyContext = dialog.textContent?.includes('Replying to');
  return hasReplyContext;
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

        // Find and click reply button
        const replyBtn = tweet.querySelector('[data-testid="reply"]');
        
        if (!replyBtn) {
          throw new Error('Reply button not found');
        }

        // Close any open dialogs first
        const existingDialog = document.querySelector('[role="dialog"]');
        if (existingDialog && !isReplyDialogOpen()) {
          const closeBtn = existingDialog.querySelector('[aria-label="Close"]') || 
                          existingDialog.querySelector('button[data-testid*="close"]');
          if (closeBtn) {
            closeBtn.click();
            await new Promise(resolve => setTimeout(resolve, 300));
          }
        }

        // Click reply button to open reply dialog
        replyBtn.click();
        
        // Wait for reply dialog to open
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        // Verify reply dialog is actually open
        let attempts = 0;
        while (!isReplyDialogOpen() && attempts < 5) {
          await new Promise(resolve => setTimeout(resolve, 300));
          attempts++;
        }
        
        if (!isReplyDialogOpen()) {
          throw new Error('Reply dialog did not open - try clicking reply manually');
        }

        // Generate reply via background worker
        const dialogRoot = document.querySelector('[role="dialog"]');
        const replyBox = getXComposerEditable(dialogRoot);
        
        if (!replyBox) {
          throw new Error('Reply box not found in dialog');
        }

        btn.innerHTML = '🤖 AI thinking...';
        const reply = await generateReply(tweetText, images);

        // Paste it
        await pasteIntoXEditor(replyBox, reply);

        const editable = getXComposerEditable(dialogRoot) || replyBox;
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
}, 1000);

const observer = new MutationObserver(() => {
  addToneSelector();
  addGenerateButtons();
});

observer.observe(document.body, {
  childList: true,
  subtree: true
});