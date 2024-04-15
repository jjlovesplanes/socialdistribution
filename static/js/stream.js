'use strict'

document.addEventListener("DOMContentLoaded", async () => {
    const githubUsername = userData.github.split('github.com/')[1];
    if (githubUsername === undefined) {
        // Could not parse GitHub username from URL
        console.log("Invalid GitHub link");
    } else {
        console.log(githubUsername)
        const response = await fetch(`https://api.github.com/users/${githubUsername}/events`);
        if (response.status === 404) {
            // User not found
            return;
        }
        const data = await response.json();
        console.log(data);

        const eventsToPost = []
        if (userData.lastPostTime !== "None") {
            for (const event of data) {
                if (event.created_at > userData.lastPostTime) {
                    // GitHub event happened after the last post the user created
                    // Retrieve data needed to create a post
                    const eventData = {
                        type: event.type,
                        repo: event.repo,
                        // Add other necessary data here...
                    }
                    console.log(eventData)
                    eventsToPost.push(eventData);
                }
            }
        }
        
        console.log(eventsToPost);
        // TODO: Make GitHub posts look better. Posts containing GitHub activity don't look great rn...
        for (const event of eventsToPost) {
            fetch(`/authors/${userData.id}/posts/`, {
                method: 'POST',
                headers: {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    'X-CSRFToken': getCookie('csrftoken'),
                },
                body: JSON.stringify({
                    title: "New GitHub Activity",
                    description: `New ${event.type} on repository ${event.repo.name}`,
                    contentType: "text/markdown",
                    content: `${event.type} by [${githubUsername}](https://github.com/${githubUsername}) on repository [${event.repo.name}](https://github.com/${event.repo.name})`,
                    visibility: "PUBLIC"
                }),
            })
        }
    }
});