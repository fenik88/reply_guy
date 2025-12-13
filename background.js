chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'generateReply') {
    fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'claude-sonnet-4-20250514',
        max_tokens: 500,
        messages: [
          {
            role: 'user',
            content: `You are an expert at crafting viral X (Twitter) replies for crypto and Polymarket content.

TWEET TO REPLY TO:
"${request.tweetText}"

TONE: ${request.tone}

Generate ONE perfect reply. The reply must:
- Be SHORT (1-2 sentences max, preferably 1)
- Use the ${request.tone} tone
- Create EMOTION (curiosity, excitement, FOMO, intrigue, controversy)
- AVOID: emojis, dots, brackets, parentheses, these words: profit, bet, money, gamble, betting, gambling, wager, odds
- Focus on: prediction markets, forecasting, events, outcomes, market wisdom, collective intelligence
- HOOK the reader to reply back or follow for more
- Be conversational and natural
- Use questions strategically to boost engagement

Return ONLY the reply text, nothing else. No quotes, no preamble, just the reply.`
          }
        ]
      })
    })
    .then(response => response.json())
    .then(data => {
      const reply = data.content[0].text.trim();
      sendResponse({ success: true, reply: reply });
    })
    .catch(error => {
      console.error('API Error:', error);
      sendResponse({ success: false, error: error.message });
    });

    return true;
  }
});