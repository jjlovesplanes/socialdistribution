'use strict'

document.addEventListener("DOMContentLoaded", async () => {
    const removeFollowerButton = document.querySelector(".remove-follower-button");
    if (removeFollowerButton !== null) {
        // No event listener necessary if Send Request or Edit Profile button is rendered
        removeFollowerButton.addEventListener('click', async () => {
            handleRemoveFollower();
        });
    }
});

async function handleRemoveFollower() {
    const response = await fetch(`/authors/${followerData.authorUUID}/followers/${followerData.userUUID}`, {
        method: "DELETE",
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken'),
        },
    }).catch(error => console.error('Error:', error));

    if (response.status === 204) {
        window.location.reload();
    } else {
        console.log("Follower could not be deleted");
    }
}