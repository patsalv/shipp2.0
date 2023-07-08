/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
      "./app/templates/**/*.html",
      "./app/static/src/**/*.js",
      "./node_modules/flowbite/**/*.js"
  ],
  theme: {
    extend: {
        colors: {
            "base-french-gray": "#C0CCD844",
            "accent-1-blue-crayola": "#687bf3ff",
            "accent-2-space-cadet": "#2d3047ff",
            "text-1-davys-grey": "#525251ff"
        }
    },
  },
  plugins: [
       require("flowbite/plugin")
  ],
}
