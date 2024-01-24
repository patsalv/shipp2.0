document.addEventListener("DOMContentLoaded", function () {
  const roomPolicyTrashBtns = document.querySelectorAll(".room-trash");
  const deviceTypeTrashButton = document.querySelectorAll(".device-type-trash");
  const alertMsg = document.getElementById("alertMsg");
  deviceTypeTrashButton.forEach(function (trashBtn) {
    trashBtn.addEventListener("click", function () {
      if (confirm("Are you sure you want to delete this device type policy?")) {
        const policyId = trashBtn.parentNode.parentNode.dataset.policyId;
        deleteCategoryPolicies(policyId);
      }
    });
  });

  roomPolicyTrashBtns.forEach(function (trashBtn) {
    trashBtn.addEventListener("click", function () {
      if (confirm("Are you sure you want to delete this room policy?")) {
        const roomId = trashBtn.parentNode.parentNode.dataset.roomId;
        const roomPolicyId = trashBtn.parentNode.parentNode.dataset.policyId;
        deleteRoomPolicy(roomId, roomPolicyId);
      }
    });
  });

  // delete funciton for room policies
  async function deleteRoomPolicy(roomId, policyId) {
    try {
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
      return response;
    } catch (e) {
      console.error(e);
      alertMsg.classList.replace("hidden", "flex");
    }
  }

  // delete functions for category policies
  async function deleteCategoryPolicies(policyId) {
    try {
      let url = undefined;
      if (window.SCRIPT_ROOT) {
        url = `${window.SCRIPT_ROOT}/device-types/policies/${policyId}`;
      } else {
        url = `/device-types/policies/${policyId}`;
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
      return response;
    } catch (e) {
      console.error(e);
      alertMsg.classList.replace("hidden", "flex");
    }
  }

  document
    .getElementById("device-type-filter-btn")
    .addEventListener("click", filterDeviceTypePolicies);

  document
    .getElementById("room-filter-btn")
    .addEventListener("click", filterRoomPolicies);

  async function filterRoomPolicies() {
    let selectedRoomId = document.getElementById("rooms").value;
    let selectedStatus = document.getElementById("room-policy-status").value;

    let roomPolicyTable = document.getElementById("room-policy-table");
    let trElements = roomPolicyTable.getElementsByTagName("tr");
    let trElementsArray = Array.from(trElements);

    let url = undefined;
    if (window.SCRIPT_ROOT) {
      url = `${window.SCRIPT_ROOT}/rooms/policies?roomId=${selectedRoomId}&status=${selectedStatus}`;
    } else {
      url = `/rooms/policies?roomId=${selectedRoomId}&status=${selectedStatus}`;
    }

    const res = await fetch(url);
    let resJson = await res.json();

    trElementsArray.slice(1).forEach(function (tr) {
      const policyId = tr.getAttribute("data-policy-id");
      if (resJson.includes(Number(policyId))) {
        tr.classList.remove("hidden");
      } else {
        tr.classList.add("hidden");
      }
    });
  }

  async function filterDeviceTypePolicies() {
    let selectedDeviceType = document.getElementById("device-types").value;
    let selectedStatus = document.getElementById(
      "device-type-policy-status"
    ).value;

    let deviceTypePolicyTable = document.getElementById("device-type-table");
    let trElements = deviceTypePolicyTable.getElementsByTagName("tr");
    let trElementsArray = Array.from(trElements);

    let url = undefined;
    if (window.SCRIPT_ROOT) {
      url = `${window.SCRIPT_ROOT}/device-types/policies?device_type=${selectedDeviceType}&status=${selectedStatus}`;
    } else {
      url = `/device-types/policies?device_type=${selectedDeviceType}&status=${selectedStatus}`;
    }
    const res = await fetch(url);
    let resJson = await res.json();

    trElementsArray.slice(1).forEach(function (tr) {
      const policyId = tr.getAttribute("data-policy-id");
      if (resJson.includes(Number(policyId))) {
        tr.classList.remove("hidden");
      } else {
        tr.classList.add("hidden");
      }
    });
  }
});
