window.addEventListener('message', async (event) => {
  if (event.data.action === 'generate') {
    const { id, tweetText, images, tone } = event.data;

    try {
      let prompt = `You are an expert at crafting viral X (Twitter) replies for crypto and Polymarket content.

TWEET TO REPLY TO:
"${tweetText}"`;

      if (images && images.length > 0) {
        prompt += `\n\nThe tweet contains ${images.length} image(s). Consider visual context in your reply.`;
      }

      prompt += `\n\nTONE: ${tone}

Generate ONE perfect reply. The reply must:
- Be SHORT (1-2 sentences max, preferably 1)
- Use the ${tone} tone
- Create EMOTION (curiosity, excitement, FOMO, intrigue, controversy)
- AVOID: emojis, dots, brackets, parentheses, these words: profit, bet, money, gamble, betting, gambling, wager, odds
- Focus on: prediction markets, forecasting, events, outcomes, market wisdom, collective intelligence
- HOOK the reader to reply back or follow for more
- Be conversational and natural
- Use questions strategically to boost engagement

Return ONLY the reply text, nothing else.`;

      const response = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model: 'claude-sonnet-4-20250514',
          max_tokens: 300,
          messages: [{ role: 'user', content: prompt }]
        })
      });

      const data = await response.json();
      const reply = data.content[0].text.trim();

      window.parent.postMessage({
        id: id,
        success: true,
        reply: reply
      }, '*');

    } catch (error) {
      console.error('Generation error:', error);
      window.parent.postMessage({
        id: id,
        success: false,
        error: error.message
      }, '*');
    }
  }
});