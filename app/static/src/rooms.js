import "flowbite";

document.addEventListener("DOMContentLoaded", function () {
  const trashBtns = document.querySelectorAll(".trash");
  const alertMsg = document.getElementById("alertMsg");

  trashBtns.forEach(function (trashBtn) {
    trashBtn.addEventListener("click", function () {
      if (confirm("Are you sure you want to delete this room?")) {
        const roomId = trashBtn.parentNode.parentNode.dataset.roomId;
        console.log("Room ID: ", roomId);
        deleteDevice(roomId);
      }
    });
  });

  async function deleteDevice(roomId) {
    try {
      let url = undefined;
      if (window.SCRIPT_ROOT) {
        url = `${window.SCRIPT_ROOT}/delete-room/${roomId}`;
      } else {
        url = `/delete-room/${roomId}`;
      }
      const response = await fetch(url, {
        method: "DELETE",
      });

      if (!response.ok) {
        console.log("Response !ok: ", response);
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      if (response.redirected) {
        console.log("Redirected to ", response.url);
        window.location = response.url;
      } else {
        throw new Error(`Redirect failed! status: ${response.status}`);
      }
      console.log("Changes saved successfully!");
      return response;
    } catch (e) {
      console.error(e);
      alertMsg.classList.replace("hidden", "flex");
    }
  }
});
