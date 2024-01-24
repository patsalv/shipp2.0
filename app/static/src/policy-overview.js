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
    .getElementById("filter-btn")
    .addEventListener("click", filterDeviceTypePolicies);

  async function filterDeviceTypePolicies() {
    let selectedDeviceType = document.getElementById("device-types").value;
    let selectedStatus = document.getElementById("policy-state").value;

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
