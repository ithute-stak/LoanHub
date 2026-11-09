using System;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
namespace LoanHub.Desktop.Services;
public static class ConnectionProbe
{
    public static Uri ParseServer(string input)
    {
        if (!Uri.TryCreate(input.Trim(), UriKind.Absolute, out var uri) || uri.Scheme != Uri.UriSchemeHttps || !string.IsNullOrWhiteSpace(uri.UserInfo) || uri.Fragment.Length > 0 || uri.Query.Length > 0)
            throw new ArgumentException("Enter a valid HTTPS server address without credentials, query or fragment.");
        return uri;
    }
    public static async Task<string> CheckAsync(Uri server, CancellationToken cancellationToken = default)
    {
        using var handler = new HttpClientHandler { AllowAutoRedirect = false, UseCookies = false };
        using var client = new HttpClient(handler) { Timeout = TimeSpan.FromSeconds(8) };
        using var req = new HttpRequestMessage(HttpMethod.Head, server);
        using var resp = await client.SendAsync(req, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
        return $"HTTPS reachable (HTTP {(int)resp.StatusCode}). Authorization not yet verified.";
    }
}
