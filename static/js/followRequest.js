function handleFollowRequest(followerId, method, authorId) {
    console.log('button clicked')
    fetch(`/authors/${authorId}/follow_request/${followerId}`, {
        method: method,
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken'),
        },
    })
    .then(response => {
        if (response.ok) {
            window.location.reload(); 
        } else {
            console.error('Failed to handle follow request');
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}