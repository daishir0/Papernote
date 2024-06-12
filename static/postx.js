document.addEventListener('DOMContentLoaded', function() {
    const buttonsContainer = document.createElement('div');
    buttonsContainer.className = 'buttons-container';

    const tweetButton = document.createElement('a');
    tweetButton.href = `https://x.com/intent/tweet?url=${encodeURIComponent(window.location.href)}`;
    tweetButton.className = 'button-link tweet-link';
    tweetButton.textContent = 'XでCommentする';

    buttonsContainer.appendChild(tweetButton);
    document.body.appendChild(buttonsContainer);
});