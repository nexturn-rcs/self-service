using Microsoft.AspNetCore.Mvc;

namespace ${{ values.repoName }}.Controllers;

[ApiController]
[Route("[controller]")]
public class HealthController : ControllerBase
{
    [HttpGet]
    public IActionResult Get()
    {
        return Ok(new { status = "ok", service = "${{ values.repoName }}" });
    }
}
