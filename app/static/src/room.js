import "flowbite";

document.addEventListener("DOMContentLoaded", function () {
  const trashBtns = document.querySelectorAll(".trash");
  const alertMsg = document.getElementById("alertMsg");
  console.log("hello ");
  trashBtns.forEach(function (trashBtn) {
    trashBtn.addEventListener("click", function () {
      if (confirm("Are you sure you want to delete policy?")) {
        const roomId = trashBtn.parentNode.parentNode.dataset.roomId;
        const policyId = trashBtn.parentNode.dataset.policyId;
        console.log("roomId: ", roomId, "policyId: ", policyId);
        deleteRoomPolicy(roomId, policyId);
      }
    });
  });

  async function deleteRoomPolicy(roomId, policyId) {
    try {
      console.log("roomId: ", roomId, "policyId: ", policyId);
      let url = undefined;
      if (window.SCRIPT_ROOT) {
        url = `${window.SCRIPT_ROOT}/room/${roomId}/policies/${policyId}`;
      } else {
        url = `/room/${roomId}/policies/${policyId}`;
      }
      const response = await fetch(url, {
        method: "DELETE",
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      if (response.redirected) {
        window.location = response.url;
      } else {
        throw new Error(`Redirect failed! status: ${response.status}`);
      }
      console.log("Room policy deleted successfully!");
      return response;
    } catch (e) {
      console.error(e);
      //   alertMsg.classList.replace("hidden", "flex");
    }
  }
});
