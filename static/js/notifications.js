'use strict'

document.addEventListener("DOMContentLoaded", async () => {
    const clearButton = document.getElementById("clear-notifications");

    clearButton.addEventListener('click', async () => {
        const response = await fetch(`/authors/${userData.id}/inbox`, {
            method: "DELETE",
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
            }
        }).catch(error => console.error('Error:', error));

        if (response.status == 204) {
            window.location.reload();
        } else {
            console.log("Inbox could not be cleared");
        }
    })
});