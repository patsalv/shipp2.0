const roomPolicyButton = document.getElementById("policy_type-0");
const deviceTypePolicyButton = document.getElementById("policy_type-1");
const roomSelector = document.getElementById("room-selector");
const deviceTypeSelector = document.getElementById("device-type-selector");

roomPolicyButton.addEventListener("click", function () {
  // Check if the clicked radio button is selected
  if (this.checked) {
    console.log("Room Policy Selected");
    roomSelector.classList.replace("hidden", "flex");
    deviceTypeSelector.classList.replace("flex", "hidden");
  }
});

deviceTypePolicyButton.addEventListener("click", function () {
  // Check if the clicked radio button is selected
  if (this.checked) {
    console.log("Device Type Policy Selected");
    deviceTypeSelector.classList.replace("hidden", "flex");
    roomSelector.classList.replace("flex", "hidden");
  }
});
