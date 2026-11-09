using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
namespace LoanHub.Desktop.Services;
public sealed record DeviceRecord(string DeviceId, DateTimeOffset CreatedAt, string? ServerUri);
// Local ID is never proof of server authorization.
public sealed class DeviceRegistration
{
    private static readonly string Folder = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "LoanHub", "Desktop");
    private static readonly string FilePath = Path.Combine(Folder, "device.dat");
    private static readonly byte[] Entropy = Encoding.UTF8.GetBytes("LoanHub.Desktop.Device.v1");
    public DeviceRecord GetOrCreate()
    {
        Directory.CreateDirectory(Folder);
        if (File.Exists(FilePath))
        {
            try
            {
                var plain = ProtectedData.Unprotect(File.ReadAllBytes(FilePath), Entropy, DataProtectionScope.CurrentUser);
                var record = JsonSerializer.Deserialize<DeviceRecord>(plain);
                if (record is null || !Guid.TryParse(record.DeviceId, out _)) throw new InvalidDataException("Invalid device identity.");
                return record;
            }
            catch (Exception e) when (e is CryptographicException or JsonException or InvalidDataException)
            { throw new InvalidDataException("Protected device identity cannot be read. Contact an administrator.", e); }
        }
        var created = new DeviceRecord(Guid.NewGuid().ToString("D"), DateTimeOffset.UtcNow, null);
        Save(created);
        return created;
    }
    public void Save(DeviceRecord record)
    {
        Directory.CreateDirectory(Folder);
        var protectedBytes = ProtectedData.Protect(JsonSerializer.SerializeToUtf8Bytes(record), Entropy, DataProtectionScope.CurrentUser);
        var temp = FilePath + ".new";
        File.WriteAllBytes(temp, protectedBytes);
        File.Move(temp, FilePath, overwrite: true);
    }
}
