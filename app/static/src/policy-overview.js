document.addEventListener("DOMContentLoaded", function () {
  const roomPolicyTrashBtns = document.querySelectorAll(".room-trash");
  const deviceTypeTrashButton = document.querySelectorAll(".device-type-trash");
  const roomPolicyEditBtns = document.querySelectorAll(".room-policy-edit");
  const deviceTypePolicyEditBtns = document.querySelectorAll(
    ".device-type-policy-edit"
  );
  const roomPolicyToggleBtns = document.querySelectorAll(".room-policy-toggle");
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

  roomPolicyEditBtns.forEach(function (editBtn) {
    editBtn.addEventListener("click", function () {
      const roomPolicyId = editBtn.parentNode.parentNode.dataset.policyId;
      editRoomPolicy(roomPolicyId);
    });
  });

  deviceTypePolicyEditBtns.forEach(function (editBtn) {
    editBtn.addEventListener("click", function () {
      const policyId = editBtn.parentNode.parentNode.dataset.policyId;
      editDeviceTypePolicy(policyId);
    });
  });

  roomPolicyToggleBtns.forEach(function (toggleBtn) {
    toggleBtn.addEventListener("load", loadRoomPolicyState(toggleBtn));
    toggleBtn.addEventListener("click", function () {
      switchRoomPolicyState(toggleBtn);
    });
  });

  async function loadRoomPolicyState(toggleBtn) {
    let status =
      toggleBtn.parentNode.parentNode.parentNode.dataset.policyStatus;

    if (status == "enabled" || status == "active") {
      toggleBtn.checked = true;
    } else {
      toggleBtn.checked = false;
    }
  }

  async function switchRoomPolicyState(toggleBtn) {
    let policyId = toggleBtn.parentNode.parentNode.parentNode.dataset.policyId;
    try {
      let url;
      if (window.SCRIPT_ROOT) {
        url = `${window.SCRIPT_ROOT}/rooms/policies/${policyId}`;
      } else {
        url = `/rooms/policies/${policyId}`;
      }

      let response = await fetch(url, { method: "PUT" });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      let resJson = await response.json();

      if (resJson.enabled) {
        toggleBtn.parentNode.parentNode.parentNode.childNodes[5].textContent =
          "Enabled";
      } else {
        toggleBtn.parentNode.parentNode.parentNode.childNodes[5].textContent =
          "Disabled";
      }
    } catch (e) {
      console.error(e);
      alertMsg.classList.replace("hidden", "flex");
    }
  }
  // delete funciton for room policies
  async function deleteRoomPolicy(roomId, policyId) {
    try {
      let url;
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
      let url;
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

  async function editRoomPolicy(policyId) {
    let url;
    if (window.SCRIPT_ROOT) {
      url = `${window.SCRIPT_ROOT}/rooms/policies/${policyId}`;
    } else {
      url = `/rooms/policies/${policyId}`;
    }

    const res = await fetch(url, { method: "GET" });

    if (!res.ok) {
      throw new Error(`HTTP error! status: ${res.status}`);
    }

    if (res.ok) {
      window.location = res.url;
    } else {
      throw new Error(`Redirect failed! status: ${res.status}`);
    }
    console.log(res);
    return res;
  }

  async function editDeviceTypePolicy(policyId) {
    console.log("hello");
    let url;
    if (window.SCRIPT_ROOT) {
      url = `${window.SCRIPT_ROOT}/device-types/policies/${policyId}`;
    } else {
      url = `/device-types/policies/${policyId}`;
    }

    const res = await fetch(url, { method: "GET" });

    if (!res.ok) {
      throw new Error(`HTTP error! status: ${res.status}`);
    }

    if (res.ok) {
      window.location = res.url;
    } else {
      throw new Error(`Redirect failed! status: ${res.status}`);
    }
    return res;
  }

  document
    .getElementById("device-type-filter-btn")
    .addEventListener("click", filterDeviceTypePolicies);

  document
    .getElementById("room-filter-btn")
    .addEventListener("click", filterRoomPolicies);

  document
    .getElementById("device-filter-btn")
    .addEventListener("click", filterDevicePolicies);

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

  async function filterDevicePolicies() {
    let selectedDeviceId = document.getElementById("devices").value;
    let selectedStatus = document.getElementById("device-policy-status").value;
    let selectedPermission = document.getElementById("permission").value;

    let devicePolicyTable = document.getElementById("device-table");
    let trElements = devicePolicyTable.getElementsByTagName("tr");
    let trElementsArray = Array.from(trElements);

    let url = undefined;
    if (window.SCRIPT_ROOT) {
      url = `${window.SCRIPT_ROOT}/devices/policies?deviceId=${selectedDeviceId}&status=${selectedStatus}&permission=${selectedPermission}`;
    } else {
      url = `/devices/policies?deviceId=${selectedDeviceId}&status=${selectedStatus}&permission=${selectedPermission}`;
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
