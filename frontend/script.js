// API base URL - This is where your Flask server is running
const API_BASE_URL = 'http://localhost:5000';

// Global variables
let map, binLevelChart;
let allBins = [];
let allAlerts = [];
let binMarkers = {}; // Object to store bin markers by ID

// Initialize the map centered on your city
function initMap() {
    // Rohini Sector-13 coordinates: 28.7402, 77.1234
    map = L.map('map').setView([28.7402, 77.1234], 16);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);
    
    return map;
}

// Function to create colored bin markers
function createBinIcon(fillLevel) {
    let color = '#2ecc71'; // Green
    if (fillLevel > 80) color = '#e74c3c'; // Red
    else if (fillLevel > 60) color = '#f39c12'; // Orange

    return L.divIcon({
        className: 'bin-marker',
        html: `<div style="background-color: ${color}; width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; border: 3px solid white; box-shadow: 0 0 10px rgba(0,0,0,0.5);">${fillLevel}%</div>`,
        iconSize: [40, 40],
        iconAnchor: [20, 20]
    });
}

// Add or update bin on map
function addBinToMap(bin) {
    const [lat, lng] = bin.location.split(',').map(Number);
    
    // If marker already exists, update it
    if (binMarkers[bin.id]) {
        binMarkers[bin.id].setIcon(createBinIcon(bin.fill_level));
        binMarkers[bin.id].setLatLng([lat, lng]);
        
        // Update popup content
        const binName = bin.name || `Smart Bin #${bin.id}`;
        binMarkers[bin.id].setPopupContent(`
            <div style="min-width: 200px;">
                <h3 style="margin: 0 0 10px 0;">${binName}</h3>
                <p><strong>Fill Level:</strong> ${bin.fill_level}%</p>
                <p><strong>Status:</strong> ${bin.fill_level > 80 ? 'Needs Immediate Attention' : bin.fill_level > 60 ? 'Getting Full' : 'Normal'}</p>
                <button style="width: 100%; margin-top: 10px; padding: 8px; background: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer;" 
                        onclick="selectBin(${bin.id})">View Details</button>
            </div>
        `);
    } else {
        // Create new marker
        const marker = L.marker([lat, lng], { 
            icon: createBinIcon(bin.fill_level) 
        }).addTo(map);
        
        // Add popup with bin information
        const binName = bin.name || `Smart Bin #${bin.id}`;
        marker.bindPopup(`
            <div style="min-width: 200px;">
                <h3 style="margin: 0 0 10px 0;">${binName}</h3>
                <p><strong>Fill Level:</strong> ${bin.fill_level}%</p>
                <p><strong>Status:</strong> ${bin.fill_level > 80 ? 'Needs Immediate Attention' : bin.fill_level > 60 ? 'Getting Full' : 'Normal'}</p>
                <button style="width: 100%; margin-top: 10px; padding: 8px; background: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer;" 
                        onclick="selectBin(${bin.id})">View Details</button>
            </div>
        `);
        
        // Store the marker reference
        binMarkers[bin.id] = marker;
    }
    
    return binMarkers[bin.id];
}

// Function to update the alert list in the sidebar
function updateAlertList(alerts) {
    const alertList = document.getElementById('alert-list');
    if (!alertList) {
        console.error('❌ alert-list element not found');
        return;
    }
    
    alertList.innerHTML = ''; // Clear the list
    
    if (alerts.length === 0) {
        alertList.innerHTML = '<li class="alert-item"><div class="alert-info"><span class="alert-type">No active alerts</span></div></li>';
    } else {
        alerts.forEach(alert => {
            const li = document.createElement('li');
            li.className = 'alert-item';
            
            const alertTypeText = {
                'overflowing_bin': 'Overflowing Bin',
                'illegal_dumping': 'Illegal Dumping',
                'broken_bin': 'Broken Bin',
                'ai_detection': 'AI Detection',
                'citizen_report': 'Citizen Report'
            }[alert.type] || alert.type;
            
            li.innerHTML = `
                <div class="alert-info">
                    <span class="alert-type">${alertTypeText}</span>
                    <span class="alert-location">${alert.location}</span>
                    <span class="alert-time">${new Date(alert.timestamp).toLocaleString()}</span>
                </div>
                <div class="alert-actions">
                    <button class="alert-btn" onclick="viewAlertDetails(${alert.id})" title="View Details">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="alert-btn" onclick="resolveAlert(${alert.id})" title="Mark as Resolved">
                        <i class="fas fa-check"></i>
                    </button>
                </div>
            `;
            
            alertList.appendChild(li);
        });
    }
    
    // Update stats
    document.getElementById('total-alerts').textContent = alerts.length;
}

// Function to create/update the chart for a selected bin
function updateBinChart(bin) {
    const ctx = document.getElementById('bin-level-chart');
    if (!ctx) {
        console.error('❌ Chart canvas element not found');
        return;
    }
    
    const binName = bin.name || `Bin #${bin.id}`;
    document.getElementById('selected-bin-name').textContent = binName;

    if (binLevelChart) {
        binLevelChart.destroy(); // Destroy the old chart before creating a new one
    }

    binLevelChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Used', 'Remaining'],
            datasets: [{
                data: [bin.fill_level, 100 - bin.fill_level],
                backgroundColor: ['#2ecc71', '#ecf0f1'],
                borderWidth: 0
            }]
        },
        options: {
            cutout: '70%',
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    enabled: false
                }
            }
        }
    });
}

// Select a bin to view details
function selectBin(binId) {
    const bin = allBins.find(b => b.id === binId);
    if (bin) {
        const binName = bin.name || `Bin #${bin.id}`;
        updateBinChart(bin);
        showNotification(`Viewing details for ${binName}`, 'info');
    }
}

// Update stats function
function updateStats(bins, alerts) {
    // Add live update animation
    document.getElementById('total-bins').classList.add('live-update');
    document.getElementById('total-alerts').classList.add('live-update');
    document.getElementById('co2-saved').classList.add('live-update');
    
    setTimeout(() => {
        document.getElementById('total-bins').classList.remove('live-update');
        document.getElementById('total-alerts').classList.remove('live-update');
        document.getElementById('co2-saved').classList.remove('live-update');
    }, 1000);
    
    document.getElementById('total-bins').textContent = bins.length;
    document.getElementById('total-alerts').textContent = alerts.length;
    document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
    
    // Calculate CO2 reduction based on actual efficiency
    const totalBins = bins.length;
    const totalAlerts = alerts.length;
    const avgFillLevel = totalBins > 0 ? bins.reduce((sum, bin) => sum + bin.fill_level, 0) / totalBins : 0;
    
    // More realistic CO2 calculation
    const co2Reduction = Math.min(100, Math.floor(
        (totalBins * 2) + // Base from bins
        (totalAlerts * 1.5) + // From alerts cleared
        (avgFillLevel * 0.3) // Efficiency from proper management
    ));
    
    document.getElementById('co2-saved').textContent = co2Reduction + '%';
    
    // Update bin status counts
    const normalBins = bins.filter(bin => bin.fill_level <= 60).length;
    const warningBins = bins.filter(bin => bin.fill_level > 60 && bin.fill_level <= 80).length;
    const criticalBins = bins.filter(bin => bin.fill_level > 80).length;
    
    document.getElementById('normal-bins').textContent = normalBins;
    document.getElementById('warning-bins').textContent = warningBins;
    document.getElementById('critical-bins').textContent = criticalBins;
    
    // Update API status
    document.getElementById('api-status').textContent = 'Connected';
    document.getElementById('api-status').style.color = 'var(--primary)';
}

// Update simulated bins with random data
function updateSimulatedBins() {
    // Keep the real bin (ID: 1) as is and update simulated bins
    const realBin = allBins.find(bin => bin.id === 1);
    allBins = realBin ? [realBin] : [];
    
    // Add/update simulated bins with random fill levels
    const locations = [
        { id: 2, coords: "28.7415,77.1220", name: "Sector-13 Park" },
        { id: 3, coords: "28.7390,77.1245", name: "Community Center" },
        { id: 4, coords: "28.7385,77.1210", name: "Market Area" },
        { id: 5, coords: "28.7420,77.1250", name: "School Road" },
        { id: 6, coords: "28.7365,77.1235", name: "Residential Block A" },
        { id: 7, coords: "28.7430,77.1205", name: "Residential Block B" },
        { id: 8, coords: "28.7370,77.1260", name: "Shopping Complex" },
        { id: 9, coords: "28.7440,77.1240", name: "Main Road" }
    ];
    
    locations.forEach(location => {
        // Find existing bin or create new one
        const existingBinIndex = allBins.findIndex(bin => bin.id === location.id);
        
        if (existingBinIndex !== -1) {
            // Update existing bin with small random change (only if it's not the real bin)
            if (allBins[existingBinIndex].id !== 1) {
                const change = Math.random() > 0.5 ? 5 : -5;
                allBins[existingBinIndex].fill_level = Math.max(0, 
                    Math.min(100, allBins[existingBinIndex].fill_level + change));
            }
        } else {
            // Create new bin with random fill level
            allBins.push({
                id: location.id,
                fill_level: Math.floor(Math.random() * 100),
                location: location.coords,
                name: location.name
            });
        }
    });
}

// Function to fetch all data from the backend
async function fetchDashboardData() {
    try {
        console.log('🔄 Fetching dashboard data...');
        const response = await axios.get(`${API_BASE_URL}/api/dashboard`);
        const data = response.data;
        console.log('✅ Data received:', data);
        
        // Update the real bin (ID: 1) with actual data if available
        if (data.bins && data.bins.length > 0) {
            const realBin = data.bins.find(bin => bin.id === 1);
            if (realBin) {
                // Update or add the real bin
                const existingBinIndex = allBins.findIndex(bin => bin.id === 1);
                if (existingBinIndex !== -1) {
                    allBins[existingBinIndex] = realBin;
                } else {
                    allBins.push(realBin);
                }
            }
        }
        
        // Update alerts
        if (data.alerts) {
            allAlerts = data.alerts;
        }

        document.getElementById("api-status").textContent = "Connected";
        document.getElementById("api-status").style.color = "var(--primary)";
    } catch (error) {
        console.error("Error fetching data:", error);
        document.getElementById("api-status").textContent = "Disconnected";
        document.getElementById("api-status").style.color = "var(--danger)";
        
        // Use simulated data as fallback
        updateSimulatedBins();
    } finally {
        // Always update simulated bins and UI
        updateSimulatedBins();
        allBins.forEach(bin => addBinToMap(bin));
        updateStats(allBins, allAlerts);
        updateAlertList(allAlerts);
    }
}

// Notification System
function showNotification(message, type = 'info') {
    // Remove any existing notifications
    const existingNotifications = document.querySelectorAll('.notification');
    existingNotifications.forEach(notif => notif.remove());
    
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'fadeOutRight 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Initialize the dashboard
document.addEventListener('DOMContentLoaded', () => {
    map = initMap();
    
    // Set to refresh data every 5 seconds
    setInterval(fetchDashboardData, 5000);
    
    // Initial data fetch
    fetchDashboardData();

    // Simulate bin status changes for simulated bins only
    setInterval(() => {
        if (allBins.length > 0) {
            // Only update simulated bins (ID > 1)
            const simulatedBins = allBins.filter(bin => bin.id > 1);
            
            if (simulatedBins.length > 0) {
                // Randomly change a simulated bin's fill level
                const randomBinIndex = Math.floor(Math.random() * simulatedBins.length);
                const changeAmount = (Math.random() - 0.5) * 20; // -10 to +10
                
                simulatedBins[randomBinIndex].fill_level = Math.max(0, Math.min(100, 
                    simulatedBins[randomBinIndex].fill_level + changeAmount));
                
                // Update the map marker
                addBinToMap(simulatedBins[randomBinIndex]);
                
                // Update stats
                updateStats(allBins, allAlerts);
            }
        }
    }, 15000); // Change every 15 seconds
});

console.log('✅ Eco-Guardian dashboard initialized!');