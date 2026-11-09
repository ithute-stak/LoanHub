using System;
using System.Windows;
using LoanHub.Desktop.Services;
namespace LoanHub.Desktop;
public partial class MainWindow : Window
{
    private readonly DeviceRegistration _devices = new();
    private DeviceRecord? _device;
    public MainWindow()
    {
        InitializeComponent();
        try
        {
            _device = _devices.GetOrCreate();
            DeviceIdBox.Text = _device.DeviceId;
            if (!string.IsNullOrWhiteSpace(_device.ServerUri)) ServerBox.Text = _device.ServerUri;
        }
        catch (Exception ex)
        {
            StatusText.Text = "Device initialization failed. " + ex.Message;
            ServerBox.IsEnabled = false; EmailBox.IsEnabled = false; PasswordInput.IsEnabled = false;
        }
    }
    private void ShowPage(string title, string explanation) { PageTitle.Text = title; PageDescription.Text = explanation; }
    private void Home_Click(object sender, RoutedEventArgs e) => ShowPage("Welcome to LoanHub", "Windows setup and identity protection are available. Authorized login and finance operations are intentionally locked.");
    private void Device_Click(object sender, RoutedEventArgs e) => ShowPage("Device registration", "The shown ID identifies this local Windows installation only. Server-side enrollment, operator assignment, revocation and signed authorization are mandatory before access.");
    private void Settings_Click(object sender, RoutedEventArgs e) => ShowPage("Connection settings", "Save the verified HTTPS base URL for your LoanHub API. Connection success does not prove user or device permissions.");
    private void Sync_Click(object sender, RoutedEventArgs e) => ShowPage("Synchronization disabled", "No financial data is read, written, pushed or pulled until server-side approval, durable outbox and conflict resolution are implemented.");
    private void SaveServer_Click(object sender, RoutedEventArgs e)
    {
        if (_device is null) return;
        try
        {
            var uri = ConnectionProbe.ParseServer(ServerBox.Text);
            _device = _device with { ServerUri = uri.AbsoluteUri };
            _devices.Save(_device);
            StatusText.Text = "HTTPS server address saved locally. Not authenticated or approved.";
        }
        catch (Exception ex) { StatusText.Text = ex.Message; }
    }
    private async void CheckServer_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var uri = ConnectionProbe.ParseServer(ServerBox.Text);
            StatusText.Text = "Checking HTTPS connectivity...";
            StatusText.Text = await ConnectionProbe.CheckAsync(uri);
        }
        catch (Exception ex) { StatusText.Text = "Connection check failed: " + ex.Message; }
    }
}
