function calculateNextPeriod() {
    let lastPeriodDate = document.getElementById("lastPeriod").value;
    
    if (!lastPeriodDate) {
        alert("Please enter your last period date.");
        return;
    }

    let lastPeriod = new Date(lastPeriodDate);
    let nextPeriod = new Date(lastPeriod);
    nextPeriod.setDate(lastPeriod.getDate() + 28); // Assuming a 28-day cycle

    let options = { year: "numeric", month: "long", day: "numeric" };
    document.getElementById("result").innerText = "Your next period is expected around: " + nextPeriod.toLocaleDateString("en-US", options);
}
