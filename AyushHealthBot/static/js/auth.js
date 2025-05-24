document.getElementById("login-btn").addEventListener("click", function() {
    let email = document.getElementById("email").value;
    let password = document.getElementById("password").value;

    fetch('/auth/login', {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
    })
    .then(response => response.json())
    .then(data => {
        if (data.access_token) {
            localStorage.setItem("token", data.access_token);
            localStorage.setItem("role", data.role);
            window.location.href = "/dashboard";
        } else {
            alert("Login Failed");
        }
    });
});
